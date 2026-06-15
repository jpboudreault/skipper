from fastapi import HTTPException


def raise_api_error(status_code: int, code: str, **params):
    raise HTTPException(status_code=status_code, detail={"code": code, "params": params})
