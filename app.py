import streamlit as st
import os
import tempfile
import math
import time
from pathlib import Path
import ffmpeg
from faster_whisper import WhisperModel
from translate import Translator
import pysrt
from gtts import gTTS
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, AudioFileClip
import base64

# App configuration
st.set_page_config(
    page_title="Video Dubbing App",
    page_icon="🎬",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #f0f2f6;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: bold;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 0.5rem;
        color: #0c5460;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🎬 Video Dubbing App")
st.markdown("**Dub your videos into multiple languages automatically - No API keys required!**")

# Supported languages
LANGUAGES = {
    'English': 'en',
    'Spanish': 'es', 
    'French': 'fr',
    'German': 'de',
    'Italian': 'it',
    'Portuguese': 'pt',
    'Russian': 'ru',
    'Japanese': 'ja',
    'Korean': 'ko',
    'Hindi': 'hi',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Bengali': 'bn',
    'Arabic': 'ar',
    'Chinese (Simplified)': 'zh',
    'Dutch': 'nl',
    'Turkish': 'tr',
    'Vietnamese': 'vi'
}

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'output_video' not in st.session_state:
    st.session_state.output_video = None

# Utility functions
def format_time(seconds):
    """Convert seconds to SRT time format"""
    hours = math.floor(seconds / 3600)
    seconds %= 3600
    minutes = math.floor(seconds / 60)
    seconds %= 60
    milliseconds = round((seconds - math.floor(seconds)) * 1000)
    seconds = math.floor(seconds)
    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:01d},{milliseconds:03d}"
    return formatted_time

def get_video_duration(video_path):
    """Get video duration in seconds"""
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        st.error(f"Error getting video duration: {e}")
        return 0

# Main processing functions
def extract_audio(video_path, audio_path):
    """Extract audio from video"""
    try:
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_path)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True
    except Exception as e:
        st.error(f"Error extracting audio: {e}")
        return False

def transcribe_audio(audio_path):
    """Transcribe audio using Whisper"""
    try:
        model = WhisperModel("small")
        segments, info = model.transcribe(audio_path)
        language = info[0]
        segments = list(segments)
        return language, segments
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return None, []

def generate_subtitle_file(segments, subtitle_path):
    """Generate subtitle file from segments"""
    try:
        text = ""
        for index, segment in enumerate(segments):
            segment_start = format_time(segment.start)
            segment_end = format_time(segment.end)
            text += f"{str(index+1)} \n"
            text += f"{segment_start} --> {segment_end} \n"
            text += f"{segment.text} \n"
            text += "\n"

        with open(subtitle_path, "w", encoding='utf-8') as f:
            f.write(text)
        return True
    except Exception as e:
        st.error(f"Error generating subtitle file: {e}")
        return False

def translate_subtitles(subtitle_path, translated_subtitle_path, target_lang, source_lang='en'):
    """Translate subtitles to target language"""
    try:
        subs = pysrt.open(subtitle_path)
        translator = Translator(to_lang=target_lang, from_lang=source_lang)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, sub in enumerate(subs):
            try:
                sub.text = translator.translate(sub.text)
                progress = (i + 1) / len(subs)
                progress_bar.progress(progress)
                status_text.text(f"Translating subtitles... {i+1}/{len(subs)}")
            except Exception as e:
                st.warning(f"Could not translate line {i+1}: {e}")
                continue
        
        subs.save(translated_subtitle_path)
        progress_bar.empty()
        status_text.empty()
        return True
    except Exception as e:
        st.error(f"Error translating subtitles: {e}")
        return False

def generate_translated_audio(translated_subtitle_path, output_audio_path, target_lang):
    """Generate audio for translated subtitles"""
    try:
        subs = pysrt.open(translated_subtitle_path)
        combined = AudioSegment.silent(duration=0)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, sub in enumerate(subs):
            start_time = sub.start.ordinal / 1000.0
            text = sub.text
            
            # Generate speech using gTTS
            try:
                tts = gTTS(text=text, lang=target_lang, slow=False)
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_mp3:
                    tts.save(temp_mp3.name)
                
                # Load and convert to consistent format
                audio = AudioSegment.from_mp3(temp_mp3.name)
                os.unlink(temp_mp3.name)
                
                # Calculate positioning
                current_duration = len(combined)
                silent_duration = start_time * 1000 - current_duration
                
                if silent_duration > 0:
                    combined += AudioSegment.silent(duration=silent_duration)
                
                combined += audio
                
            except Exception as e:
                st.warning(f"Could not generate audio for line {i+1}: {e}")
                continue
            
            progress = (i + 1) / len(subs)
            progress_bar.progress(progress)
            status_text.text(f"Generating audio... {i+1}/{len(subs)}")
        
        # Export final audio
        combined.export(output_audio_path, format="wav")
        progress_bar.empty()
        status_text.empty()
        return True
        
    except Exception as e:
        st.error(f"Error generating translated audio: {e}")
        return False

def replace_audio_track(video_path, audio_path, output_path):
    """Replace audio track in video"""
    try:
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)
        
        # Ensure audio duration matches video
        if audio.duration > video.duration:
            audio = audio.subclip(0, video.duration)
        
        video_with_new_audio = video.set_audio(audio)
        video_with_new_audio.write_videofile(
            output_path, 
            codec='libx264', 
            audio_codec='aac',
            verbose=False,
            logger=None
        )
        
        # Close clips to free memory
        video.close()
        audio.close()
        video_with_new_audio.close()
        
        return True
    except Exception as e:
        st.error(f"Error replacing audio track: {e}")
        return False

def get_file_download_link(file_path, filename):
    """Generate download link for file"""
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:video/mp4;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href

# Main app interface
st.sidebar.header("⚙️ Settings")

# File upload
uploaded_file = st.sidebar.file_uploader(
    "Upload Video File", 
    type=['mp4', 'avi', 'mov', 'mkv'],
    help="Upload a video file to dub"
)

# Language selection
col1, col2 = st.sidebar.columns(2)
with col1:
    source_lang_name = st.selectbox(
        "Source Language",
        options=list(LANGUAGES.keys()),
        index=0,
        help="Original language of the video"
    )
    source_lang = LANGUAGES[source_lang_name]

with col2:
    target_lang_name = st.selectbox(
        "Target Language", 
        options=list(LANGUAGES.keys()),
        index=10,  # Default to Hindi
        help="Language to dub into"
    )
    target_lang = LANGUAGES[target_lang_name]

# Processing options
st.sidebar.header("🎛️ Options")
keep_original_audio = st.sidebar.checkbox("Keep original audio as background", value=False)
processing_preset = st.sidebar.selectbox("Processing Speed", ["Fast", "Balanced", "High Quality"])

# Information section
st.sidebar.header("ℹ️ About")
st.sidebar.info("""
This app uses:
- **Whisper** for speech recognition
- **Google Translate** for translation
- **gTTS** for text-to-speech
- **FFmpeg** for video processing

No API keys required!
""")

# Main content area
if uploaded_file is not None:
    # Display video info
    st.header("📹 Uploaded Video")
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        video_path = tmp_file.name
    
    # Show video preview
    col1, col2 = st.columns(2)
    
    with col1:
        st.video(uploaded_file)
        st.write(f"**File:** {uploaded_file.name}")
        st.write(f"**Size:** {uploaded_file.size / (1024*1024):.2f} MB")
    
    with col2:
        duration = get_video_duration(video_path)
        if duration > 0:
            st.write(f"**Duration:** {duration:.2f} seconds")
            st.write(f"**Source Language:** {source_lang_name}")
            st.write(f"**Target Language:** {target_lang_name}")
            
            # Warning for long videos
            if duration > 300:  # 5 minutes
                st.warning("⚠️ Long video detected. Processing may take several minutes.")
            elif duration > 600:  # 10 minutes
                st.error("❌ Very long video. Consider using shorter clips for better performance.")

    # Process button
    if st.button("🎬 Start Dubbing Process", type="primary", use_container_width=True):
        st.session_state.processing = True
        
        with st.status("🚀 Processing Video...", expanded=True) as status:
            try:
                # Create temporary files
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_dir = Path(temp_dir)
                    
                    # Step 1: Extract audio
                    status.update(label="1. Extracting audio from video...")
                    audio_path = temp_dir / "extracted_audio.wav"
                    if not extract_audio(video_path, str(audio_path)):
                        st.error("Failed to extract audio")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 2: Transcribe audio
                    status.update(label="2. Transcribing audio...")
                    language, segments = transcribe_audio(str(audio_path))
                    if not segments:
                        st.error("Failed to transcribe audio")
                        st.session_state.processing = False
                        st.stop()
                    
                    st.info(f"Detected language: {language}")
                    
                    # Step 3: Generate original subtitles
                    status.update(label="3. Generating subtitles...")
                    subtitle_path = temp_dir / "original_subtitles.srt"
                    if not generate_subtitle_file(segments, str(subtitle_path)):
                        st.error("Failed to generate subtitles")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 4: Translate subtitles
                    status.update(label="4. Translating subtitles...")
                    translated_subtitle_path = temp_dir / "translated_subtitles.srt"
                    if not translate_subtitles(str(subtitle_path), str(translated_subtitle_path), target_lang, source_lang):
                        st.error("Failed to translate subtitles")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 5: Generate translated audio
                    status.update(label="5. Generating translated audio...")
                    translated_audio_path = temp_dir / "translated_audio.wav"
                    if not generate_translated_audio(str(translated_subtitle_path), str(translated_audio_path), target_lang):
                        st.error("Failed to generate translated audio")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 6: Replace audio track
                    status.update(label="6. Creating final video...")
                    output_path = temp_dir / "dubbed_video.mp4"
                    if not replace_audio_track(video_path, str(translated_audio_path), str(output_path)):
                        st.error("Failed to create final video")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Save output to session state
                    with open(output_path, "rb") as f:
                        st.session_state.output_video = f.read()
                    
                    status.update(label="✅ Processing Complete!", state="complete")
                
                st.session_state.processing = False
                
            except Exception as e:
                st.error(f"Processing failed: {str(e)}")
                st.session_state.processing = False

# Display results
if st.session_state.output_video is not None:
    st.header("🎉 Dubbing Complete!")
    
    # Create download link
    output_filename = f"dubbed_{target_lang}_{uploaded_file.name}"
    b64_video = base64.b64encode(st.session_state.output_video).decode()
    download_link = f'<a href="data:video/mp4;base64,{b64_video}" download="{output_filename}" class="stButton">📥 Download Dubbed Video</a>'
    
    st.markdown(download_link, unsafe_allow_html=True)
    
    # Show success message
    st.markdown("""
    <div class="success-box">
        <h4>✅ Success!</h4>
        <p>Your video has been successfully dubbed from <strong>{}</strong> to <strong>{}</strong>.</p>
        <p>Click the download button above to get your dubbed video.</p>
    </div>
    """.format(source_lang_name, target_lang_name), unsafe_allow_html=True)

# Instructions section
else:
    st.header("📋 How to Use")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("1. Upload")
        st.write("• Click 'Browse files'")
        st.write("• Select your video file")
        st.write("• Supported: MP4, AVI, MOV, MKV")
    
    with col2:
        st.subheader("2. Configure")
        st.write("• Select source language")
        st.write("• Choose target language")
        st.write("• Adjust settings as needed")
    
    with col3:
        st.subheader("3. Process")
        st.write("• Click 'Start Dubbing Process'")
        st.write("• Wait for processing")
        st.write("• Download your dubbed video")

# Requirements information
st.sidebar.markdown("---")
st.sidebar.header("🔧 Requirements")
st.sidebar.code("""
streamlit
faster-whisper
ffmpeg-python
translate
gtts
pysrt
pydub
moviepy
""")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center'><p>🎬 <strong>Video Dubbing App</strong> • ⚡ <strong>No API Keys Required</strong></p></div>",
    unsafe_allow_html=True
)
