# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота в контейнер
COPY . .

# Указываем команду для запуска бота
# Убедитесь, что имя файла совпадает с вашим (например, bot.py)
CMD ["python", "bot_with_admin.py"]