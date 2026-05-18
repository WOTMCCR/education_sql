"""
图片上传 MinIO + chunk 内路径替换

图片处理流程：
  1. 文档转换时(docx_converter)将 .docx 内嵌图片导出到临时目录
  2. 本模块将这些图片上传到 MinIO 对象存储
  3. 将 chunk 中的本地图片路径替换为 MinIO URL

MinIO 中的对象组织结构：
  {bucket}/documents/{doc_id}/images/{image_name}

  例如：
  education-knowledge/documents/a1b2c3d4/images/figure1.png

为什么图片不存到 MongoDB GridFS?
  GridFS 将文件切成 255KB 的 chunk 存到两个 collection 中，
  读取时需要重组，不适合直接通过 URL 提供给前端展示。
  MinIO 兼容 S3 协议，图片可以直接通过 HTTP URL 访问。
"""

import logging
import mimetypes
from pathlib import Path

from knowledge.core.clients import ensure_minio_bucket, get_minio
from knowledge.core.config import get_settings

logger = logging.getLogger(__name__)


def _upload_single_image(
    doc_id: str,
    img_path: Path,
    *,
    bucket_name: str,
    base_url: str,
    client,
) -> tuple[str, str] | None:
    """上传单张图片；失败时记录日志并返回 None。"""
    object_key = f"documents/{doc_id}/images/{img_path.name}"
    content_type = (
        mimetypes.guess_type(str(img_path))[0]
        or "application/octet-stream"
    )

    try:
        client.fput_object(
            bucket_name=bucket_name,
            object_name=object_key,
            file_path=str(img_path),
            content_type=content_type,
        )
    except Exception as e:
        logger.warning("图片上传失败: %s — %s", img_path.name, e)
        return None

    logger.debug("图片上传成功: %s → %s", img_path.name, object_key)
    url = f"{base_url}/{bucket_name}/{object_key}"
    return img_path.name, url

def upload_images(
    doc_id: str,
    image_paths: list[Path],
)->dict[str , str]:
    """
    将图片文件上传到 MinIO，返回 {本地路径 → MinIO URL} 的映射。

    参数：
        doc_id:       文档 ID，用于构造 MinIO 对象路径
        image_paths:  本地图片文件路径列表

    返回：
        dict[str, str]
        key = 图片文件名（用于匹配 Markdown 中的引用路径）
        value = MinIO 完整 URL

    失败处理：
        单张图片上传失败不阻断整个流程。
        失败的图片记录 warning 日志，在返回的映射中不包含该图片。
    """
    if not image_paths:
        return {}
    
    s = get_settings()
    ensure_minio_bucket()
    client = get_minio()

    path_map : dict[str , str] = {}
    for img_path in image_paths:
        uploaded = _upload_single_image(
            doc_id,
            img_path,
            bucket_name=s.minio_bucket,
            base_url=s.minio_base_url,
            client=client,
        )
        if uploaded is None:
            continue

        image_name, url = uploaded
        path_map[image_name] = url

    logger.info(
        "图片上传完成: doc_id=%s, 成功 %d/%d",
        doc_id, len(path_map), len(image_paths),
    )
    return path_map

def replace_image_refs(
    chunks: list,
    path_map: dict[str, str],
) -> None:
    """
    将 chunk 中的本地图片路径替换为 MinIO URL（原地修改）。

    `chunk.image_refs` 在 chunk_document 阶段保存的是 Markdown 中的原始图片引用
    （如 "images/fig1.png"）。本函数执行后，会把：
      1. chunk_text 中的本地路径替换成 MinIO URL
      2. image_refs 中的原始路径替换成可访问的 MinIO URL

    示例：
      chunk_text 中的 "![](images/fig1.png)"
      替换为 "![](http://minio:9000/education-knowledge/documents/xxx/images/fig1.png)"
    """
    if not path_map:
        return

    for chunk in chunks:
        updated_refs = []
        for ref in chunk.image_refs:
            filename = Path(ref).name
            minio_url = path_map.get(filename)

            if minio_url is None:
                updated_refs.append(ref)
                continue

            # 优先替换 chunk_text 中记录的原始引用路径，避免把
            # images/arch.png 替成 images/http://... 这种拼接错误。
            if ref in chunk.chunk_text:
                chunk.chunk_text = chunk.chunk_text.replace(ref, minio_url)
            elif filename in chunk.chunk_text:
                chunk.chunk_text = chunk.chunk_text.replace(filename, minio_url)

            updated_refs.append(minio_url)

        chunk.image_refs = updated_refs
