"""FastAPI entrypoint."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import APP_PORT
from .errors import AppError
from .response import fail
from .routers.cart import router as cart_router
from .routers.consultations import router as consultations_router
from .routers.coupons import router as coupons_router
from .routers.courses import router as courses_router
from .routers.enrollments import router as enrollments_router
from .routers.favorites import router as favorites_router
from .routers.interactions import router as interactions_router
from .routers.orders import router as orders_router
from .routers.payments import router as payments_router
from .routers.study import router as study_router
from .routers.tickets import router as tickets_router
from .routers.users import router as users_router

OPENAPI_TAGS = [
    {"name": "users", "description": "1. 用户信息与学习档案查询"},
    {"name": "courses", "description": "2. 课程与班次查询"},
    {"name": "favorites", "description": "3. 收藏"},
    {"name": "consultations", "description": "4. 咨询"},
    {"name": "coupons", "description": "5. 优惠券"},
    {"name": "cart", "description": "6. 购物车"},
    {"name": "orders", "description": "7. 订单"},
    {"name": "payments", "description": "8. 支付与退款"},
    {"name": "enrollments", "description": "9. 报名关系与学习中心"},
    {"name": "study", "description": "10. 课次、视频、作业、考试"},
    {"name": "interactions", "description": "11. 互动与评价"},
    {"name": "tickets", "description": "12. 工单与售后服务"},
]

app = FastAPI(title="Edu Data API", version="0.1.0", openapi_tags=OPENAPI_TAGS)

app.include_router(users_router)
app.include_router(courses_router)
app.include_router(favorites_router)
app.include_router(consultations_router)
app.include_router(coupons_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(payments_router)
app.include_router(enrollments_router)
app.include_router(study_router)
app.include_router(interactions_router)
app.include_router(tickets_router)


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=fail(exc.code, exc.message),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=fail("VALIDATION_ERROR", str(exc)),
    )


@app.exception_handler(ValueError)
async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content=fail("BAD_REQUEST", str(exc)))


@app.get("/health")
def health() -> dict[str, object]:
    return {"code": 0, "message": "ok", "data": {"status": "ok"}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=APP_PORT, reload=False)
