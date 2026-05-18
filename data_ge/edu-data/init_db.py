"""初始化数据库"""

import asyncio
import os
from pathlib import Path

import asyncmy
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel
from sqlacodegen.generators import DeclarativeGenerator
from sqlalchemy import MetaData, create_engine

# 路径常量
CURRENT_DIR = Path(__file__).parent  # 当前文件所在目录
ROOT_DIR = CURRENT_DIR  # 根目录

load_dotenv(ROOT_DIR / ".env", override=False)


class DBInit:
    def __init__(self, cfg):
        self.config = None
        self.db_url = ""

    async def check_db_exists(self, db_name: str) -> bool:
        """检查数据库是否存在"""
        raise NotImplementedError

    async def delete_db(self, db_name: str):
        """删除数据库"""
        raise NotImplementedError

    async def create_db(self, db_name: str):
        """创建数据库"""
        raise NotImplementedError

    async def exec_sql_file(self, db_name: str, sql_file_path: Path):
        """执行 SQL 文件"""
        raise NotImplementedError

    def get_sync_db_url(self, db_name: str):
        """获取同步数据库连接 url"""
        raise NotImplementedError

    def get_async_db_url(self, db_name: str):
        """获取异步数据库连接 url"""
        raise NotImplementedError

    async def gen_tb_model(self, output_path: Path, db_url: str):
        """生成 SQLAlchemy 表模型"""
        # 创建 SQLAlchemy 数据库引擎
        engine = create_engine(db_url)
        # 创建元数据对象并反射数据库结构
        metadata = MetaData()
        metadata.reflect(engine)
        # 使用 DeclarativeGenerator 生成模型代码
        generator = DeclarativeGenerator(metadata, engine, [])
        code = generator.generate()
        # 将生成的代码写入文件
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)

    async def init_db(self, db_sql_orm: list[tuple], max_workers: int = 5):
        """初始化数据库并导入数据"""
        logger.info(f"开始初始化数据库 {[db_name for db_name, _, _ in db_sql_orm]}")
        semaphore = asyncio.Semaphore(max_workers)  # 信号量控制并发

        async def process_database(
            db_name: str, sql_file_path: Path, output_path: Path | None
        ):
            """处理单个数据库的异步任务"""
            async with semaphore:
                try:
                    # 检查数据库是否存在
                    if await self.check_db_exists(db_name):
                        # 删除数据库
                        await self.delete_db(db_name)
                    # 创建数据库
                    await self.create_db(db_name)
                    # 执行 SQL 文件
                    await self.exec_sql_file(db_name, sql_file_path)
                    # 生成表模型
                    if output_path:
                        await self.gen_tb_model(
                            output_path, self.get_sync_db_url(db_name)
                        )
                finally:
                    logger.info(f"{db_name} 初始化完成")

        # 并发执行任务
        await asyncio.gather(
            *[
                process_database(db_name, sql_file_path, output_path)
                for db_name, sql_file_path, output_path in db_sql_orm
            ]
        )


class MySQLCfg(BaseModel):
    host: str
    port: int
    user: str
    password: str


class MyInit(DBInit):
    """MySQL 数据库初始化"""

    def __init__(self, cfg: MySQLCfg):
        self.config = cfg
        self.conn_conf = cfg.model_dump()

    async def check_db_exists(self, db_name: str) -> bool:
        try:
            conn = await asyncmy.connect(**self.conn_conf)
            try:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                        "WHERE SCHEMA_NAME = %s",
                        (db_name,),
                    )
                    result = await cur.fetchone()
                    return result is not None
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"检查数据库存在性失败: {e}")
            return False

    async def delete_db(self, db_name: str):
        conn = await asyncmy.connect(**self.conn_conf, autocommit=True)
        try:
            async with conn.cursor() as cur:
                await cur.execute(f"DROP DATABASE `{db_name}`")
        except Exception as e:
            logger.exception(f"数据库 {db_name} 删除失败: {e}")
        finally:
            conn.close()

    async def create_db(self, db_name: str):
        conn = await asyncmy.connect(**self.conn_conf, autocommit=True)
        try:
            async with conn.cursor() as cur:
                await cur.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4")
        except Exception as e:
            logger.exception(f"数据库 {db_name} 创建失败: {e}")
        finally:
            conn.close()

    async def exec_sql_file(self, db_name: str, sql_file_path: Path):
        with open(sql_file_path, "r", encoding="utf-8") as f:
            sql = f.read()
        conn = await asyncmy.connect(**self.conn_conf, db=db_name)
        try:
            await conn.begin()
            async with conn.cursor() as cur:
                statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
                for statement in statements:
                    await cur.execute(statement)
                await conn.commit()
        except Exception as e:
            await conn.rollback()
            logger.exception(f"{sql_file_path.stem} 执行sql失败: {e}")
        finally:
            conn.close()

    def get_sync_db_url(self, db_name: str):
        return (
            "mysql+pymysql://"
            f"{self.config.user}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{db_name}"
        )

    def get_async_db_url(self, db_name: str):
        return (
            "mysql+asyncmy://"
            f"{self.config.user}:{self.config.password}"
            f"@{self.config.host}:{self.config.port}/{db_name}"
        )


def prepare():
    """获取 (数据库名, SQL 脚本文件路径, 表模型输出路径) 元组"""
    # SQL 文件目录
    sql_dir = ROOT_DIR / "sql"
    # 获取所有 SQL 文件，每个 SQL 文件作为一个数据库，SQL 文件中是数据库中所有的表
    sql_files = list(sql_dir.glob("*.sql"))
    # db_name, sql_file_path, output_path
    db_sql_orm = []
    for f in sql_files:
        db_name = f.stem
        sql_file_path = f
        output_path = None
        # output_path = ROOT_DIR / "app" / "entities" / f"{db_name}.py"
        db_sql_orm.append((db_name, sql_file_path, output_path))
    return db_sql_orm


if __name__ == "__main__":
    db_init = MyInit(
        MySQLCfg(
            host=os.getenv("DB_HOST", ""),
            port=int(os.getenv("DB_PORT", "")),
            user=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASSWORD", ""),
        )
    )
    asyncio.run(db_init.init_db(prepare()))
