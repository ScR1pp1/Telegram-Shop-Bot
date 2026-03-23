from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from sqlalchemy import or_, select

from app.database import SessionFactory
from app.models import Faq


router = Router()


@router.inline_query()
async def faq_inline(inline_query: InlineQuery):
    q = (inline_query.query or "").strip()
    async with SessionFactory() as s:
        stmt = select(Faq).where(Faq.is_active.is_(True)).order_by(Faq.order, Faq.id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(Faq.question.ilike(like), Faq.answer.ilike(like)))
        stmt = stmt.limit(10)
        res = await s.execute(stmt)
        faqs = list(res.scalars().all())

    results: list[InlineQueryResultArticle] = []
    for f in faqs:
        desc = (f.answer or "")[:50]
        results.append(
            InlineQueryResultArticle(
                id=str(f.id),
                title=f.question,
                description=desc,
                input_message_content=InputTextMessageContent(message_text=f.answer),
            )
        )
    await inline_query.answer(results, cache_time=1, is_personal=True)

