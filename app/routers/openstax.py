import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.models.account import UserAccount
from app.services.openstax_store import OpenStaxBook, OpenStaxStore
from app.services.pdf_service import PDFService
from app.services.vector_store import VectorStoreService
from app.dependencies import (
    get_settings,
    get_pdf_service,
    get_vector_store_service,
    get_openstax_store,
    require_admin,
)

logger = logging.getLogger("llm_tutor.openstax.router")
router = APIRouter(prefix="/api/openstax", tags=["openstax"])


@router.get("/books")
async def list_books(
    openstax_store: OpenStaxStore = Depends(get_openstax_store),
):
    """List all available OpenStax books."""
    books = openstax_store.list_books()
    return {"books": [b.model_dump(mode="json") for b in books]}


@router.post("/upload")
async def upload_openstax_book(
    file: UploadFile = File(...),
    pdf_service: PDFService = Depends(get_pdf_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    openstax_store: OpenStaxStore = Depends(get_openstax_store),
    admin: UserAccount = Depends(require_admin),
):
    """Upload an OpenStax book PDF to the shared library."""
    settings = get_settings()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Save to openstax directory
        upload_dir = Path(settings.openstax.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)

        # Parse PDF
        text, toc_entries = pdf_service.parse_pdf(file_path)
        if not text.strip():
            file_path.unlink()
            raise HTTPException(status_code=400, detail="PDF contains no extractable text")

        # Create book entry
        title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()
        book = OpenStaxBook(
            title=title,
            file_name=file.filename,
        )

        # Chunk using the configured strategy
        from app.services.chunking import AutoChunkingStrategy
        chunker = AutoChunkingStrategy()
        chunks = chunker.chunk(
            text,
            book.id,
            file_name=file.filename,
            toc_entries=toc_entries if toc_entries else None,
            chunk_size=settings.openstax.chunk_size,
            chunk_overlap=settings.openstax.chunk_overlap,
        )

        # Index into the openstax collection
        indexed = await vector_store.index_chunks(
            chunks,
            collection_name=settings.openstax.collection_name,
        )

        book.chunk_count = indexed
        openstax_store.add_book(book)

        logger.info(
            "Uploaded OpenStax book '%s': %d chunks indexed",
            title, indexed,
        )

        return {
            "book_id": book.id,
            "title": title,
            "file_name": file.filename,
            "chunk_count": indexed,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("OpenStax upload failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")


@router.delete("/books/{book_id}")
async def delete_openstax_book(
    book_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    openstax_store: OpenStaxStore = Depends(get_openstax_store),
    admin: UserAccount = Depends(require_admin),
):
    """Delete an OpenStax book and its chunks."""
    settings = get_settings()
    book = openstax_store.remove_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Delete chunks from vector store
    await vector_store.delete_by_material_id(
        book_id,
        collection_name=settings.openstax.collection_name,
    )

    # Delete file
    file_path = Path(settings.openstax.upload_dir) / book.file_name
    if file_path.exists():
        file_path.unlink()

    return {"status": "deleted", "book_id": book_id}


@router.post("/books/{book_id}/reindex")
async def reindex_openstax_book(
    book_id: str,
    pdf_service: PDFService = Depends(get_pdf_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    openstax_store: OpenStaxStore = Depends(get_openstax_store),
    admin: UserAccount = Depends(require_admin),
):
    """Re-index an OpenStax book: delete old chunks, re-parse, re-chunk, re-embed."""
    settings = get_settings()
    book = openstax_store.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    file_path = Path(settings.openstax.upload_dir) / book.file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Book PDF file not found on disk")

    try:
        # Delete old chunks
        await vector_store.delete_by_material_id(
            book_id,
            collection_name=settings.openstax.collection_name,
        )

        # Re-parse
        text, toc_entries = pdf_service.parse_pdf(file_path)

        # Re-chunk
        from app.services.chunking import AutoChunkingStrategy
        chunker = AutoChunkingStrategy()
        chunks = chunker.chunk(
            text,
            book.id,
            file_name=book.file_name,
            toc_entries=toc_entries if toc_entries else None,
            chunk_size=settings.openstax.chunk_size,
            chunk_overlap=settings.openstax.chunk_overlap,
        )

        # Re-index
        indexed = await vector_store.index_chunks(
            chunks,
            collection_name=settings.openstax.collection_name,
        )

        # Update metadata
        book.chunk_count = indexed
        openstax_store.save()

        logger.info("Re-indexed OpenStax book '%s': %d chunks", book.title, indexed)

        return {
            "book_id": book.id,
            "title": book.title,
            "chunk_count": indexed,
            "status": "reindexed",
        }
    except Exception as e:
        logger.error("Re-index failed for book %s: %s", book_id, e)
        raise HTTPException(status_code=500, detail=f"Re-index failed: {e}")
