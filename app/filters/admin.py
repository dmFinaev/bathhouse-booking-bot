from aiogram.filters import BaseFilter
from app.config import settings

class IsAdminFilter(BaseFilter):
    async def __call__(self, message):
        return settings.is_admin(message.from_user.id)
