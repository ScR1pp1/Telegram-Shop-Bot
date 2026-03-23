from __future__ import annotations

import time
import logging
from typing import Any, Optional
from sqlalchemy import select

from app.database import SessionFactory
from app.models import Category, Product

logger = logging.getLogger(__name__)


class CategoryCache:
    """Кэш для категорий с временем жизни"""
    
    def __init__(self, ttl_seconds: int = 60):
        self.cache: dict[str, tuple[float, Any]] = {}
        self.ttl = ttl_seconds
        logger.info(f"CategoryCache initialized with TTL={ttl_seconds}s")

    async def get_root_categories(self) -> list[Category]:
        """Получить корневые категории с кэшированием"""
        cache_key = "root_categories"
        now = time.time()
        
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if now - timestamp < self.ttl:
                logger.debug("Returning root categories from cache")
                return data
        
        logger.info("Loading root categories from database")
        async with SessionFactory() as s:
            res = await s.execute(
                select(Category)
                .where(Category.parent_id.is_(None))
                .order_by(Category.order, Category.name)
            )
            data = list(res.scalars().all())
        
        self.cache[cache_key] = (now, data)
        return data
    
    async def get_child_categories(self, category_id: int) -> list[Category]:
        """Получить дочерние категории с кэшированием"""
        cache_key = f"child_categories_{category_id}"
        now = time.time()
        
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if now - timestamp < self.ttl:
                logger.debug(f"Returning child categories for {category_id} from cache")
                return data
        
        logger.info(f"Loading child categories for {category_id} from database")
        async with SessionFactory() as s:
            res = await s.execute(
                select(Category)
                .where(Category.parent_id == category_id)
                .order_by(Category.order, Category.name)
            )
            data = list(res.scalars().all())
        
        self.cache[cache_key] = (now, data)
        return data
    
    async def get_category(self, category_id: int) -> Optional[Category]:
        """Получить категорию по ID с кэшированием"""
        cache_key = f"category_{category_id}"
        now = time.time()
        
        if cache_key in self.cache:
            timestamp, data = self.cache[cache_key]
            if now - timestamp < self.ttl:
                logger.debug(f"Returning category {category_id} from cache")
                return data
        
        logger.info(f"Loading category {category_id} from database")
        async with SessionFactory() as s:
            res = await s.execute(select(Category).where(Category.id == category_id))
            data = res.scalar_one_or_none()
        
        self.cache[cache_key] = (now, data)
        return data
    
    async def invalidate(self, key: Optional[str] = None):
        """Очистить кэш"""
        if key:
            self.cache.pop(key, None)
            logger.info(f"Cache invalidated for key: {key}")
        else:
            self.cache.clear()
            logger.info("Full cache invalidated")


category_cache = CategoryCache(ttl_seconds=60)