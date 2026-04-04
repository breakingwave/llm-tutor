import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.models.account import UserAccount
from app.services.openstax_service import OpenStaxService
from app.dependencies import (
    get_openstax_service,
    require_admin,
)

logger = logging.getLogger("llm_tutor.openstax.router")
router = APIRouter(prefix="/api/openstax", tags=["openstax"])


@router.get("/books")
async def list_books(
    openstax_service: OpenStaxService = Depends(get_openstax_service),
):
    """List all available OpenStax books."""
    books = openstax_service.list_books()
    return {"books": [b.model_dump(mode="json") for b in books]}


@router.post("/upload")
async def upload_openstax_book(
    file: UploadFile = File(...),
    openstax_service: OpenStaxService = Depends(get_openstax_service),
    admin: UserAccount = Depends(require_admin),
):
    """Upload an OpenStax book PDF to the shared library."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()
        book = await openstax_service.upload_book(file.filename, content)

        return {
            "book_id": book.id,
            "title": book.title,
            "file_name": file.filename,
            "chunk_count": book.chunk_count,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("OpenStax upload failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.delete("/books/{book_id}")
async def delete_openstax_book(
    book_id: str,
    openstax_service: OpenStaxService = Depends(get_openstax_service),
    admin: UserAccount = Depends(require_admin),
):
    """Delete an OpenStax book and its chunks."""
    try:
        await openstax_service.delete_book(book_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Book not found")

    return {"status": "deleted", "book_id": book_id}


@router.post("/books/{book_id}/reindex")
async def reindex_openstax_book(
    book_id: str,
    openstax_service: OpenStaxService = Depends(get_openstax_service),
    admin: UserAccount = Depends(require_admin),
):
    """Re-index an OpenStax book: delete old chunks, re-parse, re-chunk, re-embed."""
    try:
        book = await openstax_service.reindex_book(book_id)

        return {
            "book_id": book.id,
            "title": book.title,
            "chunk_count": book.chunk_count,
            "status": "reindexed",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Re-index failed for book %s: %s", book_id, e)
        raise HTTPException(status_code=500, detail=f"Re-index failed: {e}")
