from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="服务根接口")
def root():
    return {"message": "feihualing API is running"}


@router.get("/hello/{name}", summary="示例问候接口")
def say_hello(name: str):
    return {"message": f"Hello {name}"}
