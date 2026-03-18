# app/database/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, 
    Text, DateTime, ForeignKey, JSON, BigInteger
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional, List

from .base import Base, TimestampMixin


class Bathhouse(Base, TimestampMixin):
    """Модель бани"""
    __tablename__ = 'bathhouses'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Основная информация
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    address: Mapped[Optional[str]] = mapped_column(String(200))
    
    # Контакты владельца (строка для Telegram username или телефона)
    owner_contact: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_name: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Цены и вместимость
    max_guests: Mapped[int] = mapped_column(Integer, default=4)
    price_per_hour: Mapped[Optional[int]] = mapped_column(Integer)  # в рублях
    min_booking_hours: Mapped[int] = mapped_column(Integer, default=2)
    
    # Особенности (храним как JSON для гибкости)
    features: Mapped[dict] = mapped_column(
        JSON,
        default={
            'has_pool': False,
            'has_grill': False,
            'has_karaoke': False,
            'has_hookah': False,
            'has_parking': True,
            'has_billiard': False,
            'has_kitchen': True,
            'has_tv': True,
            'has_wifi': True,
            'has_air_conditioning': False,
            'has_fireplace': False,
            'has_terrace': False
        }
    )
    
    # Фотографии (file_id из Telegram)
    photo_ids: Mapped[List[str]] = mapped_column(JSON, default=[])
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)  # одобрено админом
    
    # Связи
    applications: Mapped[List["Application"]] = relationship(
        "Application", 
        back_populates="bathhouse",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Bathhouse {self.id}: {self.name}>"
    
    @property
    def features_list(self) -> List[str]:
        """Возвращает список активных фич"""
        active_features = []
        feature_names = {
            'has_pool': 'Бассейн',
            'has_grill': 'Мангал',
            'has_karaoke': 'Караоке',
            'has_hookah': 'Кальян',
            'has_parking': 'Парковка',
            'has_billiard': 'Бильярд',
            'has_kitchen': 'Кухня',
            'has_tv': 'Телевизор',
            'has_wifi': 'Wi-Fi',
            'has_air_conditioning': 'Кондиционер',
            'has_fireplace': 'Камин',
            'has_terrace': 'Терраса'
        }
        
        for key, value in self.features.items():
            if value and key in feature_names:
                active_features.append(feature_names[key])
        
        return active_features


class Application(Base, TimestampMixin):
    """Модель заявки на бронирование"""
    __tablename__ = 'applications'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Ссылка на баню
    bathhouse_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey('bathhouses.id', ondelete='CASCADE')
    )
    
    # Информация о клиенте
    client_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    client_username: Mapped[Optional[str]] = mapped_column(String(100))
    client_phone: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Детали заявки
    message: Mapped[Optional[str]] = mapped_column(Text)
    guests_count: Mapped[int] = mapped_column(Integer, default=2)
    desired_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    hours_count: Mapped[int] = mapped_column(Integer, default=2)
    
    # Статус заявки
    status: Mapped[str] = mapped_column(
        String(20), 
        default='pending',  # pending, contacted, confirmed, cancelled, completed
        index=True
    )
    
    # Ответ владельца
    owner_response: Mapped[Optional[str]] = mapped_column(Text)
    response_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Связи
    bathhouse: Mapped["Bathhouse"] = relationship(
        "Bathhouse", 
        back_populates="applications"
    )
    
    def __repr__(self):
        return f"<Application {self.id} for Bathhouse {self.bathhouse_id}>"
    
    @property
    def formatted_desired_date(self) -> Optional[str]:
        """Форматированная дата для отображения"""
        if self.desired_date:
            return self.desired_date.strftime("%d.%m.%Y %H:%M")
        return None


class User(Base, TimestampMixin):
    """Модель пользователя бота (для статистики)"""
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    language_code: Mapped[Optional[str]] = mapped_column(String(10))
    
    # Статистика
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_activity: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    applications_count: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self):
        return f"<User {self.telegram_id}: {self.first_name}>"