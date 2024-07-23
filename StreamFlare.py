import os
import logging
from yt_dlp import YoutubeDL
from mutagen.id3 import ID3, APIC
from mutagen.easyid3 import EasyID3
import requests
import subprocess
import shutil
from pyfiglet import figlet_format
from tqdm import tqdm
import time

# Configure logging
logging.basicConfig(level=logging.INFO)

def sanitize_filename(filename):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)

def convert_file(input_file, output_file):
    logging.info(f"Converting {input_file} to {output_file}")
    subprocess.run(['ffmpeg', '-i', input_file, output_file], check=True)
    os.remove(input_file)

def get_file_size(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File {file_path} does not exist.")
    return os.path.getsize(file_path) / (1024 * 1024)  # Convert bytes to megabytes

def add_metadata_to_audio(file_path, title, artist, album=None, genre=None, year=None, thumbnail_url=None):
    try:
        audio = EasyID3(file_path)
        audio['title'] = title
        audio['artist'] = artist
        if album:
            audio['album'] = album
        if genre:
            audio['genre'] = genre
        if year:
            audio['date'] = year
        audio.save()

        if thumbnail_url:
            thumbnail_data = requests.get(thumbnail_url).content
            audio = ID3(file_path)
            audio['APIC'] = APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover',
                data=thumbnail_data
            )
            audio.save()
    except Exception as e:
        logging.error(f"Failed to add metadata: {e}")

def download_youtube(link, output_dir, file_format, custom_filename=None, retries=3):
    for attempt in range(retries):
        try:
            logging.info(f"Downloading from link: {link}")

            audio_formats = ['mp3', 'flac', 'm4a', 'wav', 'aac', 'ogg', 'opus']
            video_formats = ['mp4', 'mkv', 'avi', 'webm', 'mov', 'flv', 'wmv', '3gp']

            if file_format in audio_formats:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(output_dir, 'temp_audio.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': file_format,
                        'preferredquality': '192',
                    }],
                    'noplaylist': True,
                }
            elif file_format in video_formats:
                ydl_opts = {
                    'format': 'bestvideo+bestaudio/best',
                    'outtmpl': os.path.join(output_dir, 'temp_video.%(ext)s'),
                    'noplaylist': True,
                }
            else:
                raise ValueError("Invalid format specified.")
            
            temp_files = [os.path.join(output_dir, f'temp_audio.{ext}') for ext in audio_formats] + \
                         [os.path.join(output_dir, f'temp_video.{ext}') for ext in video_formats]
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(link, download=True)
                video_title = info_dict.get('title', 'Unknown Title')
                video_uploader = info_dict.get('uploader', 'Unknown Uploader')
                thumbnail_url = info_dict.get('thumbnail')

                temp_file = os.path.join(output_dir, f'temp_audio.{file_format}' if file_format in audio_formats else 'temp_video.webm')
                final_file = os.path.join(output_dir, sanitize_filename(custom_filename) if custom_filename else sanitize_filename(f"{video_title}.{file_format}"))

                if not os.path.exists(temp_file):
                    raise FileNotFoundError(f"Temporary file {temp_file} does not exist.")

                if file_format in video_formats:
                    if file_format == 'mkv':
                        if not os.path.exists(temp_file):
                            raise FileNotFoundError(f"Temporary file {temp_file} does not exist.")
                        os.rename(temp_file, final_file)
                    else:
                        temp_video_file = os.path.join(output_dir, 'temp_video.webm')
                        if not os.path.exists(temp_video_file):
                            raise FileNotFoundError(f"Temporary video file {temp_video_file} does not exist.")
                        os.rename(temp_video_file, final_file)
                else:
                    if os.path.splitext(temp_file)[1][1:] != file_format:
                        convert_file(temp_file, final_file)
                    else:
                        os.rename(temp_file, final_file)

                if file_format in audio_formats:
                    add_metadata_to_audio(final_file, video_title, video_uploader, thumbnail_url=thumbnail_url)

            return final_file
        except FileNotFoundError as fnf_error:
            logging.error(f"Attempt {attempt + 1} failed: {fnf_error}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise

def progress_bar(iterable, total, desc="Processing"):
    for i, item in enumerate(tqdm(iterable, desc=desc, total=total, unit='item')):
        yield item

def main():
    try:
        ascii_art = figlet_format("StreamFlare", font='small')
        print(ascii_art)
    except Exception as e:
        logging.error(f"Error generating ASCII art: {e}")
        print("StreamFlare")

    formats = ['mp3', 'flac', 'm4a', 'wav', 'aac', 'ogg', 'opus', 'mp4', 'mkv', 'avi', 'webm', 'mov', 'flv', 'wmv', '3gp']
    file_format = input(f"What format do you want? ({', '.join(formats)}): ").strip().lower()
    if file_format not in formats:
        print(f"Choose one of the available formats: {', '.join(formats)}!")
        return

    links = input("Enter YouTube links (comma-separated for batch processing): ").split(',')
    output_dir = input("Enter the output directory (leave blank for current directory): ").strip()
    output_dir = output_dir or os.getcwd()

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            logging.error(f"Failed to create output directory {output_dir}: {e}")
            print(f"Failed to create output directory: {e}")
            return

    custom_filename = input("Enter a custom filename (optional): ").strip()
    open_after_download = input("Open file after download? (yes/no): ").strip().lower() == "yes"
    
    total_links = len(links)
    for link in progress_bar(links, total_links, desc="Downloading"):
        try:
            output_file = download_youtube(link.strip(), output_dir, file_format, custom_filename)
            if output_file:
                file_size = get_file_size(output_file)
                logging.info(f"Downloaded and saved as {output_file} ({file_size:.2f} MB)")
                print(f"Downloaded and saved as {output_file} ({file_size:.2f} MB)")
                
                if open_after_download:
                    subprocess.run(['start', '', output_file], shell=True)
                
        except Exception as e:
            logging.error(f"An error occurred while processing {link}: {e}")

if __name__ == "__main__":
    main()
