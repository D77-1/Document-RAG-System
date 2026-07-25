from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from app.services.doc_service import DocService
from app.schemas.doc import UploadResponse, DocListResponse

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    文档上传与解析接口
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    # Simple extension check
    allowed_exts = [".pdf", ".docx", ".doc", ".md", ".markdown", ".txt"]
    import os
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail=f"Unsupported file format. Allowed: {allowed_exts}")

    return await DocService.process_doc(file)

@router.get("/docs/list", response_model=DocListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(6, ge=1, le=100, description="Items per page"),
    keyword: str = Query("", description="Search keyword for filename")
):
    """
    获取已上传文档列表 (支持分页和模糊查询)
    """
    return DocService.get_doc_list(page=page, size=size, keyword=keyword)

@router.post("/docs/reindex/{doc_id}")
async def reindex_document(doc_id: str):
    """
    重新索引指定文档
    """
    success = DocService.reindex_doc(doc_id)
    if not success:
        raise HTTPException(status_code=500, detail="Reindexing failed")
    return {"status": "success", "message": "Document reindexed"}

@router.get("/docs/content/{doc_id}")
async def get_doc_content(doc_id: str):
    """Get parsed content of a document"""
    content = DocService.get_doc_content(doc_id)
    return {"content": content}

@router.get("/docs/file/{doc_id}")
async def get_doc_file(doc_id: str):
    """Get raw file stream"""
    file_path = DocService.get_doc_path(doc_id)
    return FileResponse(file_path)

@router.delete("/docs/{doc_id}")
async def delete_document(doc_id: str, background_tasks: BackgroundTasks):
    """
    删除文档 (同时删除本地文件和更新索引)
    """
    success = DocService.delete_doc(doc_id, background_tasks)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "success", "message": "Document deleted"}
