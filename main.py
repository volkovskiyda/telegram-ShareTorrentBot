import os, dotenv, shutil, asyncio, ffmpeg
from warnings import filterwarnings
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, Bot
from telegram.ext import filters, Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler
from telegram.warnings import PTBUserWarning
from telegram.error import InvalidToken
import libtorrent as lt
from torrentp import TorrentDownloader

dotenv.load_dotenv()
filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

ACCEPT_TORRENT, SELECT_AUDIO, SAMPLE, UPLOAD = range(4)

torrent = "torrent"
downloads = "downloads"

token = os.getenv("BOT_TOKEN")
base_url = os.getenv("BASE_URL") or "http://localhost:8081"
timeout = os.getenv("READ_TIMEOUT") or 30
upload_chat_id = os.getenv("UPLOAD_CHAT_ID")
available_user_ids = os.getenv("AVAILABLE_USER_IDS")

video_exts = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v")

async def start(update, _):
    message = update.message
    username = message.from_user["username"]
    await message.reply_text(f"Hey, @{username}.\n"
                             "Welcome to Share Torrent bot\n"
                             "Upload a valid .torrent file to start download\n\n"
                             "/help - for more details")


async def help(update, _) -> None:
    await update.message.reply_markdown("Upload a valid .torrent file to start download")


async def unknown(update, _):
    await update.message.reply_text("Unknown command. Please type /help for available commands")


async def cancel(update, _) -> int:
    await update.message.reply_text("Cancelled", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def select_torrent(update, context) -> int:
    user_id = update.effective_user.id

    if available_user_ids and str(user_id) not in available_user_ids.split(","):
        await update.message.reply_text("You are not authorized to use this bot")
        return ConversationHandler.END

    message = update.message
    document = message.document
    file_name = document.file_name if document else None
    if not document or not file_name.lower().endswith(".torrent") or not document.mime_type.startswith("application/") or not document.mime_type.endswith("torrent"):
        await message.reply_text("Please attach a valid .torrent file.")
        return ConversationHandler.END

    torrents = "torrents"

    os.makedirs(torrents, exist_ok=True)
    torrent_path = os.path.join(torrents, file_name)
    file = await context.bot.get_file(document.file_id)

    try:
        file_path = await file.download_to_drive(torrent_path)
        print(f"download_to_drive: {file_path}")
    except InvalidToken:
        file_path = "./home/" + file.file_path.split("//home/")[-1]
        torrent_path = file_path
    except Exception as e:
        await message.reply_text(f"Failed to download torrent file: {e}")
        return ConversationHandler.END

    file_name = document.file_name
    downloads_dir = f"{downloads}/{file_name}"

    torrent_data = {
        "file_path": file_path,
        "path": torrent_path,
        "torrent_name": file_name,
        "downloads_dir": downloads_dir,
        "file_count": None,
        "total_size": None,
        "files": [],
    }

    try:
        ti = lt.torrent_info(torrent_path)
        files = ti.files()
        total_size = 0
        listed_files = []

        for idx in range(files.num_files()):
            fpath = files.file_path(idx)
            fsize = files.file_size(idx)
            total_size += fsize
            listed_files.append({"path": fpath, "size": fsize})

        torrent_data["file_count"] = files.num_files()
        torrent_data["total_size"] = total_size
        torrent_data["files"] = listed_files
    except:
        # Fallback if libtorrent parsing fails
        torrent_data["file_count"] = "unknown"
        torrent_data["total_size"] = "unknown"
        torrent_data["files"] = []

    size_str = (
        f"{torrent_data["total_size"] / (1024 ** 3):.2f} GB" if isinstance(torrent_data.get("total_size"), int) else "unknown"
    )
    file_count = torrent_data.get("file_count", "unknown")

    file_lines = []
    for f in (torrent_data.get("files") or [])[:10]:
        file_lines.append(f"- {f["path"]} ({f["size"] / (1024 ** 2):.2f} MB)")
    more_note = ""
    if torrent_data.get("files") and len(torrent_data["files"]) > 10:
        more_note = f"\n… and {len(torrent_data["files"]) - 10} more"

    info_text = (
        f"Torrent: {file_name}\n"
        f"Total size: {size_str}\n"
        f"File count: {file_count}\n"
    )
    if file_lines:
        info_text += "\nFiles:\n" + "\n".join(file_lines) + more_note

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, proceed", callback_data="accept:yes"),
                InlineKeyboardButton("No, cancel", callback_data="accept:no"),
            ]
        ]
    )

    context.user_data[torrent] = torrent_data

    await message.reply_text(info_text, reply_markup=keyboard)
    return ACCEPT_TORRENT

async def accept_torrent(update, context) -> int:
    query = update.callback_query
    await query.answer()
    decision = (query.data or "").split(":")[-1]

    if decision == "no":
        await query.edit_message_text("Cancelled.")
        return ConversationHandler.END

    await query.edit_message_text("Accepted. Downloading torrent file...")

    torrent_data = context.user_data.get(torrent, {})
    file_path = torrent_data.get("file_path")
    downloads_dir = torrent_data.get("downloads_dir")
    os.makedirs(downloads_dir, exist_ok=True)

    downloader = TorrentDownloader(f"./{file_path}", downloads_dir)
    await downloader.start_download()

    await query.edit_message_text("Torrent downloaded")

    listdir = [f for f in os.listdir(downloads_dir) if os.path.isdir(f"{downloads_dir}/{f}")]
    if len(listdir) == 0:
        directory = downloads_dir
        files = video_files(downloads_dir)
        name = files[0] if files else ""
        sample_name = name
        first_file = f"{downloads_dir}/{sample_name}"
    elif len(listdir) == 1:
        first_dir = listdir[0]
        directory = f"{downloads_dir}/{first_dir}"
        files = video_files(directory)
        name = first_dir
        sample_name = files[0] if files else ""
        first_file = f"{directory}/{sample_name}"
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Error: multiple directories in downloads folder",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if len(files) == 0:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Error: no video files in downloads folder",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    context.user_data["name"] = name
    context.user_data["sample_name"] = sample_name
    context.user_data["first_file"] = first_file
    context.user_data["directory"] = directory

    file_title = ""
    try:
        probe_info = ffmpeg.probe(first_file)
        fmt = probe_info.get("format") or {}
        file_title = fmt.get("tags", {}).get("title") or ""
        streams = [s for s in (probe_info.get("streams") or []) if s.get("codec_type") == "audio"]

        built_tracks = []
        for i, s in enumerate(streams):
            tags = s.get("tags") or {}
            lang = (tags.get("language") or "").lower()
            title = tags.get("title")
            codec = s.get("codec_long_name") or s.get("codec_name")
            channels = s.get("channels")
            layout = s.get("channel_layout")

            parts = []
            core = []
            if title: parts.append(title)
            if lang: core.append(lang)
            if codec: core.append(codec)
            if channels: core.append(f"{channels}ch")
            if layout: core.append(layout)
            label = (f"{" - ".join(parts)}: " if parts else "") + f"Track {i + 1} ({", ".join(core)})"

            built_tracks.append({"index": i, "label": label})

        audio_tracks = built_tracks
    except:
        audio_tracks = []

    context.user_data["audio_tracks"] = audio_tracks

    if audio_tracks and len(audio_tracks) > 1:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(a["label"], callback_data=f"audio:{a["index"]}")]
                for a in audio_tracks
            ]
        )
        await query.edit_message_text(
            f"{sample_name}\n{file_title}\nSelect an audio track:",
            reply_markup=keyboard,
        )
        return SELECT_AUDIO

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, continue", callback_data="sample:yes"),
                InlineKeyboardButton("No, cancel", callback_data="sample:no"),
            ]
        ]
    )
    await query.edit_message_text("Do you want to create a short sample (about 1 minute)?", reply_markup=keyboard)
    return SAMPLE


async def select_audio(update, context) -> int:
    query = update.callback_query
    await query.answer()
    data = (query.data or "")
    try:
        sel_index = int(data.split(":")[-1])
    except:
        sel_index = 0

    context.user_data["selected_audio_index"] = sel_index

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, continue", callback_data="sample:yes"),
                InlineKeyboardButton("No, cancel", callback_data="sample:no"),
            ]
        ]
    )
    await query.edit_message_text("Do you want to create a short sample (about 1 minute)?", reply_markup=keyboard)
    return SAMPLE


async def sample(update, context) -> int:
    query = update.callback_query
    await query.answer()
    decision = (query.data or "").split(":")[-1]

    if decision == "no":
        await query.edit_message_text("Processing cancelled.")
        return ConversationHandler.END

    await query.edit_message_text("Great! Continuing processing...")

    user_data = context.user_data
    sample_name = user_data.get("sample_name")
    first_file = user_data.get("first_file")
    selected_audio_index = user_data.get("selected_audio_index")

    sample_dir = "sample"
    os.makedirs(sample_dir, exist_ok=True)
    output_path = os.path.join(sample_dir, f"{sample_name}.mp4")

    pipeline = ffmpeg_pipeline(first_file, output_path, selected_audio_index, True)

    try:
        await asyncio.to_thread(pipeline.run)
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode("utf-8", errors="ignore") if hasattr(e, "stderr") and e.stderr else str(e)
        await query.edit_message_text(
            f"Failed to convert video via ffmpeg.\n{err_msg[-1200:]}"
        )
        return ConversationHandler.END

    await query.edit_message_text(f"Sample created: {output_path}.\nUploading...")

    probe = ffmpeg.probe(output_path)
    fmt = probe.get("format") or {}
    duration = float(fmt.get("duration") or 0.0)
    width_and_height = width_height(probe)
    width, height = width_and_height.split("x")

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes, continue", callback_data="upload:yes"),
                InlineKeyboardButton("No, cancel", callback_data="upload:no"),
            ]
        ]
    )

    await context.bot.send_video(
        chat_id=query.message.chat_id,
        video=open(output_path, "rb"),
        width=width,
        height=height,
        duration=duration,
        caption=f"Sample of {sample_name}\nOriginal: {width_height(ffmpeg.probe(first_file))}\nScaled: {width_and_height}\nUpload full version?",
        reply_markup=keyboard,
    )
    shutil.rmtree(sample_dir, ignore_errors=True)

    return UPLOAD

async def upload(update, context) -> int:
    query = update.callback_query
    await query.answer()

    try: await query.edit_message_reply_markup(reply_markup=None)
    except: pass

    decision = (query.data or "").split(":")[-1]

    if decision == "no":
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Upload cancelled.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    message = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Great! Converting original video to mp4...",
        reply_markup=ReplyKeyboardRemove(),
    )

    user_data = context.user_data
    name = user_data.get("name")
    directory = user_data.get("directory")
    selected_audio_index = user_data.get("selected_audio_index")

    upload_dir = f"upload/{directory}"
    os.makedirs(upload_dir, exist_ok=True)

    for f in video_files(directory):
        pipeline = ffmpeg_pipeline(os.path.join(directory, f), os.path.join(upload_dir, f"{f}.mp4"), selected_audio_index, False)
        await asyncio.to_thread(pipeline.run)

    files = sorted([file for file in os.listdir(upload_dir) if file.endswith('.mp4')])
    len_files = len(files)
    videos = f" {len_files} videos" if len_files > 1 else ""
    text = f"- Successfully converted:\n{name}.\nUploading{videos}..."
    try:
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=message.message_id,
            text=text,
        )
    except:
        await context.bot.send_message(chat_id=query.message.chat_id, text=text)

    chat_id = upload_chat_id or query.message.chat_id

    for file in files:
        await retry(
            target=send_video,
            target_args=(context.bot, chat_id, file, os.path.join(upload_dir, file)),
            error_target=send_message,
            error_target_args=(context.bot, query.message.chat_id, f"Failed to upload video file: {file}"),
            retries=3,
        )
    shutil.rmtree(upload_dir, ignore_errors=True)
    print(f"Uploaded {name}, upload folder removed: {upload_dir}")
    return ConversationHandler.END

async def send_video(bot: Bot, chat_id: str, file: str, video: str):
    probe = ffmpeg.probe(video)
    try:
        duration = float(probe['format']['duration'])
    except:
        duration = None
    width_and_height = width_height(probe)
    width, height = width_and_height.split("x")
    await bot.send_video(
        chat_id=chat_id,
        caption=file,
        video=video,
        filename=file,
        duration=duration,
        width=width,
        height=height,
    )

async def send_message(bot: Bot, chat_id: str, text: str):
    await bot.send_message(chat_id=chat_id, text=text)

async def retry(
    target = None, target_args = (),
    error_target = None, error_target_args = (),
    retries = 3,
):
    for i in range(retries):
        try:
            await target(*target_args)
            break
        except Exception as e:
            print(f"Error: {e}")
            if i == retries - 1:
                if error_target: await error_target(*error_target_args)
                raise e

def video_files(path: str):
    return [f for f in os.listdir(path) if f.lower().endswith(video_exts)]

def main():
    application = (
        Application.builder()
        .token(token)
        .base_url(f"{base_url}/bot")
        .read_timeout(float(timeout))
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))

    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.ATTACHMENT, select_torrent)],
        states={
            ACCEPT_TORRENT: [CallbackQueryHandler(accept_torrent)],
            SELECT_AUDIO: [CallbackQueryHandler(select_audio)],
            SAMPLE: [CallbackQueryHandler(sample)],
            UPLOAD: [CallbackQueryHandler(upload)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    application.run_polling()

def width_height(probe):
    try:
        video_stream = probe["streams"][0]
        width = int(video_stream["width"])
        height = int(video_stream["height"])
    except:
        width = None
        height = None
    return f"{width}x{height}"

def ffmpeg_pipeline(input_file, output_file, selected_audio_index, create_sample):
    if create_sample:
        probe = ffmpeg.probe(input_file)
        fmt = probe.get("format") or {}
        duration = float(fmt.get("duration") or 0.0)
        if duration <= 0:
            start_sec = 0.0
        else:
            start_sec = max(0.0, duration * 0.10)
        input_stream = ffmpeg.input(input_file, ss=start_sec)
    else:
        input_stream = ffmpeg.input(input_file)

    video = input_stream.video
    if os.path.getsize(input_file) >> 20 > 4000:
        v_stream = video.filter("scale", "round(iw/4)*2", "round(ih/4)*2")
    else:
        v_stream = video
    if os.path.getsize(input_file) >> 20 > 2000:
        vcodec = "libx264"
    else:
        vcodec = "copy"
    if isinstance(selected_audio_index, int):
        a_stream = input_stream[f"a:{selected_audio_index}"]
    else:
        a_stream = input_stream.audio

    if create_sample:
        output = ffmpeg.output(
            v_stream,
            a_stream,
            output_file,
            t=120,
            vcodec=vcodec,
            acodec="aac",
            movflags="+faststart",
            format="mp4",
            shortest=None,
        )
    else:
        output = ffmpeg.output(
            v_stream,
            a_stream,
            output_file,
            vcodec=vcodec,
            acodec="aac",
            movflags="+faststart",
            format="mp4",
            shortest=None,
        )

    return output.overwrite_output()

if __name__ == "__main__":
    main()
