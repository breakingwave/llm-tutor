import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.models.account import UserAccount
from app.models.material import Material, MaterialSource
from app.services.pdf_service import PDFService
from app.services.session_store import SessionStore
from app.services.user_store import UserStore
from app.services.vector_store import VectorStoreService
from app.dependencies import (
    get_current_user,
    get_session_store,
    get_settings,
    get_pdf_service,
    get_user_store,
    get_vector_store_service,
)

logger = logging.getLogger("llm_tutor.pdf.router")
router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    store: SessionStore = Depends(get_session_store),
    pdf_service: PDFService = Depends(get_pdf_service),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    user: UserAccount = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
):
    """Upload a PDF, parse, chunk, and embed into vector store."""
    if session_id not in user.session_ids and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Check upload size limit
    settings = get_settings()
    max_bytes = settings.auth.max_upload_bytes_per_user
    content_bytes = await file.read()
    await file.seek(0)
    file_size = len(content_bytes)
    if user.total_upload_bytes + file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload would exceed {max_bytes // (1024**3)}GB limit. "
            f"Current usage: {user.total_upload_bytes / (1024**2):.1f}MB",
        )

    try:
        # Save file
        file_path = await pdf_service.save_upload(file, session_id)

        # Parse PDF
        text, toc_entries = pdf_service.parse_pdf(file_path)
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF contains no extractable text")

        # Create material
        title = Path(file.filename).stem.replace("_", " ").replace("-", " ").title()
        material = Material(
            source=MaterialSource.PDF_UPLOAD,
            title=title,
            file_name=file.filename,
            content=text[:5000],  # store first 5000 chars as preview
            metadata={
                "file_path": str(file_path),
                "total_length": len(text),
                "toc_entries": len(toc_entries),
            },
        )

        # Chunk
        chunks = pdf_service.chunk_pdf(text, toc_entries, file.filename, material.id)

        # Embed and index
        indexed = await vector_store.index_chunks(chunks, session_id=session_id)

        # Store material in session
        session_data.materials.append(material)
        store.save(session_id)

        # Track upload bytes for quota
        user_store.update_upload_bytes(user.id, file_size)

        logger.info(
            "Uploaded PDF '%s': %d chunks indexed for session %s",
            file.filename, indexed, session_id,
        )

        return {
            "material_id": material.id,
            "title": title,
            "file_name": file.filename,
            "chunk_count": indexed,
            "text_length": len(text),
            "toc_entries": len(toc_entries),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("PDF upload failed: %s", e)
        raise HTTPException(status_code=500, detail=f"PDF processing failed: {e}")


@router.get("/pdfs/{session_id}")
async def list_pdfs(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    """List uploaded PDFs for a session."""
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    pdfs = [
        {
            "material_id": m.id,
            "title": m.title,
            "file_name": m.file_name,
            "created_at": m.created_at.isoformat(),
            "text_length": m.metadata.get("total_length", 0),
            "toc_entries": m.metadata.get("toc_entries", 0),
        }
        for m in session_data.materials
        if m.source == MaterialSource.PDF_UPLOAD
    ]
    return {"pdfs": pdfs}


@router.delete("/pdfs/{session_id}/{material_id}")
async def delete_pdf(
    session_id: str,
    material_id: str,
    store: SessionStore = Depends(get_session_store),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
    user: UserAccount = Depends(get_current_user),
    user_store: UserStore = Depends(get_user_store),
):
    """Delete a PDF and its chunks from the vector store."""
    if session_id not in user.session_ids and user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find and remove material
    material = next(
        (m for m in session_data.materials if m.id == material_id),
        None,
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Delete chunks from vector store
    await vector_store.delete_by_material_id(material_id, session_id=session_id)

    # Delete file if it exists and track size reduction
    file_path = material.metadata.get("file_path")
    if file_path:
        path = Path(file_path)
        if path.exists():
            file_size = path.stat().st_size
            path.unlink()
            user_store.update_upload_bytes(user.id, -file_size)

    # Remove from session
    session_data.materials = [m for m in session_data.materials if m.id != material_id]
    store.save(session_id)

    return {"status": "deleted", "material_id": material_id}


class AddManualMaterialRequest(BaseModel):
    session_id: str
    title: str
    content: str
    url: str | None = None


@router.post("/manual")
async def add_manual_material(
    request: AddManualMaterialRequest,
    store: SessionStore = Depends(get_session_store),
):
    """Add a manual material entry."""
    session_data = store.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    material = Material(
        source=MaterialSource.USER_UPLOAD,
        title=request.title,
        content=request.content,
        url=request.url,
    )
    session_data.materials.append(material)
    store.save(request.session_id)

    return material.model_dump(mode="json")


@router.delete("/{session_id}/{material_id}")
async def delete_material(
    session_id: str,
    material_id: str,
    store: SessionStore = Depends(get_session_store),
    vector_store: VectorStoreService = Depends(get_vector_store_service),
):
    """Delete any material and its chunks from the vector store."""
    session_data = store.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")

    material = next(
        (m for m in session_data.materials if m.id == material_id),
        None,
    )
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Delete chunks from vector store
    await vector_store.delete_by_material_id(material_id, session_id=session_id)

    # Delete file if it's a PDF upload
    if material.source == MaterialSource.PDF_UPLOAD:
        file_path = material.metadata.get("file_path")
        if file_path:
            path = Path(file_path)
            if path.exists():
                path.unlink()

    # Remove from session
    session_data.materials = [m for m in session_data.materials if m.id != material_id]
    store.save(session_id)

    return {"status": "deleted", "material_id": material_id}
