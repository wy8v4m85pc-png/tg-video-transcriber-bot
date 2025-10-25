import os
import asyncio
import tempfile
import subprocess
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Missing BOT_TOKEN or OPENAI_API_KEY environment variable")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = OpenAI(api_key=OPENAI_API_KEY)

def remove_subtitles(video_path, output_path):
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-map", "0", "-map", "-0:s", "-c", "copy", output_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    except subprocess.CalledProcessError:
        subprocess.run(["cp", video_path, output_path], check=True)

def extract_audio(video_path, audio_path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-ac", "1", "-ar", "16000", "-vn", audio_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
    )

def transcribe_and_translate(audio_path):
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(model="whisper-1", file=f).text
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Translate this text to Russian clearly."},
            {"role": "user", "content": transcript}
        ],
        temperature=0
    )
    return transcript, completion.choices[0].message.content.strip()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("👋 Отправь видео, я удалю субтитры, распознаю речь и переведу на русский.")

@dp.message(F.video | F.document)
async def handle_video(message: Message):
    await message.answer("⏳ Обработка видео...")
    file = await bot.get_file((message.video or message.document).file_id)

    with tempfile.TemporaryDirectory() as td:
        video_path = os.path.join(td, "in.mp4")
        audio_path = os.path.join(td, "audio.wav")
        clean_path = os.path.join(td, "clean.mp4")

        await bot.download_file(file.file_path, destination=video_path)
        remove_subtitles(video_path, clean_path)
        extract_audio(clean_path, audio_path)
        text, ru = transcribe_and_translate(audio_path)

        await message.answer(f"🗣 Распознанный текст:\n{text}\n\n🇷🇺 Перевод:\n{ru}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
