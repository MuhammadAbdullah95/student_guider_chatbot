from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from database import SessionLocal
from routers.auth_utils import get_current_user
from openai import OpenAI

router = APIRouter(prefix="/chats", tags=["Messages"])

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{chat_id}/message", response_model=schemas.MessageOut)
def send_message(
    chat_id: int,
    message: schemas.MessageCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    # 🔐 1. Check if chat belongs to user
    chat = db.query(models.Chat).filter_by(id=chat_id, user_id=user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # 📝 2. Save user's message
    user_msg = models.Message(chat_id=chat.id, role="user", content=message.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 🧠 3. Get full message history for context
    messages = db.query(models.Message).filter_by(chat_id=chat.id).order_by(models.Message.created_at.asc()).all()
    formatted = [{"role": m.role, "content": m.content} for m in messages]

    # 🤖 4. Call OpenAI (or Gemini) LLM
    openai_client = OpenAI(api_key="your-openai-api-key")

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=formatted
        )
        assistant_reply = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {e}")

    # 💾 5. Save assistant message
    assistant_msg = models.Message(chat_id=chat.id, role="assistant", content=assistant_reply)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # ✨ 6. Update chat title if it's still the default
    if chat.title == "New Chat":
        try:
            title_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Generate a short, clear title for this conversation."},
                    {"role": "user", "content": message.content}
                ]
            )
            new_title = title_response.choices[0].message.content.strip().replace('"', '')
            chat.title = new_title
            db.commit()
        except Exception as e:
            print(f"[Warning] Failed to auto-generate title: {e}")

    return assistant_msg
