import streamlit as st
import os
import tempfile
import math
import time
from pathlib import Path
import subprocess
import sys

# Install required packages
def install_packages():
    packages = [
        "faster-whisper", "ffmpeg-python", "translate", 
        "gtts", "pysrt", "pydub", "moviepy"
    ]
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            st.warning(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Install packages when app starts
if "packages_installed" not in st.session_state:
    with st.spinner("Installing required packages..."):
        install_packages()
    st.session_state.packages_installed = True

# Now import the packages
from faster_whisper import WhisperModel
import ffmpeg
from translate import Translator
import pysrt
from gtts import gTTS
from pydub import AudioSegment
from moviepy.editor import VideoFileClip, AudioFileClip

# App configuration
st.set_page_config(
    page_title="Audio Dubbing App",
    page_icon="🎙️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        background-color: #f0f2f6;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        color: #155724;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        color: #856404;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

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

def extract_audio(video_path, audio_output_path):
    """Extract audio from video file"""
    try:
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_output_path)
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        return True
    except Exception as e:
        st.error(f"Error extracting audio: {e}")
        return False

def transcribe_audio(audio_path, model_size="small"):
    """Transcribe audio using Whisper"""
    try:
        model = WhisperModel(model_size)
        segments, info = model.transcribe(audio_path)
        language = info[0]
        segments = list(segments)
        return language, segments
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return None, None

def generate_subtitle_file(segments, subtitle_path):
    """Generate SRT subtitle file from segments"""
    try:
        text = ""
        for index, segment in enumerate(segments):
            segment_start = format_time(segment.start)
            segment_end = format_time(segment.end)
            text += f"{str(index+1)} \n"
            text += f"{segment_start} --> {segment_end} \n"
            text += f"{segment.text} \n"
            text += "\n"

        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except Exception as e:
        st.error(f"Error generating subtitle file: {e}")
        return False

def translate_subtitles(subtitle_path, output_path, target_lang, source_lang="en"):
    """Translate subtitles to target language"""
    try:
        subs = pysrt.open(subtitle_path)
        translator = Translator(to_lang=target_lang, from_lang=source_lang)
        
        for sub in subs:
            try:
                translated_text = translator.translate(sub.text)
                sub.text = translated_text
            except Exception as e:
                st.warning(f"Could not translate: {sub.text}. Error: {e}")
                continue

        subs.save(output_path, encoding='utf-8')
        return True
    except Exception as e:
        st.error(f"Error translating subtitles: {e}")
        return False

def generate_translated_audio(subtitle_path, output_audio_path, target_lang):
    """Generate translated audio with proper timing"""
    try:
        subs = pysrt.open(subtitle_path)
        combined = AudioSegment.silent(duration=0)

        for sub in subs:
            start_time = sub.start.ordinal / 1000.0  # convert to seconds
            text = sub.text

            if text.strip():  # Only process non-empty text
                # Generate speech using gTTS
                tts = gTTS(text=text, lang=target_lang, slow=False)
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                    temp_path = temp_file.name
                
                tts.save(temp_path)
                
                # Load the temporary mp3 file
                audio = AudioSegment.from_mp3(temp_path)
                
                # Calculate the position to insert the audio
                current_duration = len(combined)
                silent_duration = start_time * 1000 - current_duration

                if silent_duration > 0:
                    # Add silence to fill the gap
                    combined += AudioSegment.silent(duration=silent_duration)

                # Append the audio to the combined AudioSegment
                combined += audio
                
                # Cleanup temporary file
                os.unlink(temp_path)

        # Export the combined audio
        combined.export(output_audio_path, format="wav")
        return True
    except Exception as e:
        st.error(f"Error generating translated audio: {e}")
        return False

def replace_audio_track(video_path, audio_path, output_path):
    """Replace audio track in video"""
    try:
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)
        
        # Set the new audio to the video
        video_with_new_audio = video.set_audio(audio)
        
        # Write the final video
        video_with_new_audio.write_videofile(
            output_path, 
            codec='libx264', 
            audio_codec='aac',
            verbose=False,
            logger=None
        )
        
        # Close the clips to free memory
        video.close()
        audio.close()
        video_with_new_audio.close()
        
        return True
    except Exception as e:
        st.error(f"Error replacing audio track: {e}")
        return False

# Language mapping for gTTS
LANGUAGE_CODES = {
    "English": "en",
    "Spanish": "es", 
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Hindi": "hi",
    "Tamil": "ta",
    "Telugu": "te",
    "Malayalam": "ml",
    "Kannada": "kn",
    "Bengali": "bn",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Punjabi": "pa",
    "Urdu": "ur",
    "Arabic": "ar",
    "Chinese (Simplified)": "zh-CN",
    "Japanese": "ja",
    "Korean": "ko",
    "Russian": "ru"
}

# Main App
st.title("🎙️ Audio Dubbing App")
st.markdown("**Dub your videos automatically without external APIs!**")

# File upload section
st.header("1. Upload Video File")
uploaded_file = st.file_uploader(
    "Choose a video file", 
    type=['mp4', 'avi', 'mov', 'mkv', 'wmv'],
    help="Supported formats: MP4, AVI, MOV, MKV, WMV"
)

# Language selection
st.header("2. Select Languages")
col1, col2 = st.columns(2)

with col1:
    source_lang = st.selectbox(
        "Source Language (Original Video)",
        options=list(LANGUAGE_CODES.keys()),
        index=0,
        help="Language spoken in the original video"
    )

with col2:
    target_lang = st.selectbox(
        "Target Language (Dubbed)",
        options=list(LANGUAGE_CODES.keys()),
        index=7,  # Default to Hindi
        help="Language for the dubbed audio"
    )

# Processing options
st.header("3. Processing Options")
model_size = st.selectbox(
    "Speech Recognition Model Size",
    options=["tiny", "base", "small", "medium"],
    index=2,
    help="Larger models are more accurate but slower"
)

# Process button
if st.button("🚀 Start Dubbing Process", type="primary"):
    if uploaded_file is not None:
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Step 1: Save uploaded file
            st.subheader("📥 Step 1: Processing uploaded video")
            video_path = temp_path / "original_video.mp4"
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"Video uploaded: {uploaded_file.name}")
            
            # Initialize progress
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 2: Extract audio
            status_text.text("🎵 Step 2: Extracting audio from video...")
            audio_path = temp_path / "extracted_audio.wav"
            if extract_audio(str(video_path), str(audio_path)):
                progress_bar.progress(20)
                st.success("Audio extracted successfully!")
            else:
                st.error("Failed to extract audio")
                st.stop()
            
            # Step 3: Transcribe audio
            status_text.text("📝 Step 3: Transcribing audio...")
            source_lang_code = LANGUAGE_CODES[source_lang]
            target_lang_code = LANGUAGE_CODES[target_lang]
            
            language, segments = transcribe_audio(str(audio_path), model_size)
            if segments:
                progress_bar.progress(40)
                st.success(f"Audio transcribed! Detected language: {language}")
                
                # Display some transcription samples
                with st.expander("View Transcription Samples"):
                    for i, segment in enumerate(segments[:5]):  # Show first 5 segments
                        st.write(f"[{format_time(segment.start)} -> {format_time(segment.end)}] {segment.text}")
            else:
                st.error("Failed to transcribe audio")
                st.stop()
            
            # Step 4: Generate original subtitles
            status_text.text("📄 Step 4: Generating subtitles...")
            original_subtitle_path = temp_path / "original_subtitles.srt"
            if generate_subtitle_file(segments, str(original_subtitle_path)):
                progress_bar.progress(60)
                st.success("Original subtitles generated!")
            else:
                st.error("Failed to generate subtitles")
                st.stop()
            
            # Step 5: Translate subtitles
            status_text.text("🌐 Step 5: Translating subtitles...")
            translated_subtitle_path = temp_path / "translated_subtitles.srt"
            if translate_subtitles(
                str(original_subtitle_path), 
                str(translated_subtitle_path), 
                target_lang_code, 
                source_lang_code
            ):
                progress_bar.progress(80)
                st.success("Subtitles translated!")
            else:
                st.error("Failed to translate subtitles")
                st.stop()
            
            # Step 6: Generate translated audio
            status_text.text("🎙️ Step 6: Generating translated audio...")
            translated_audio_path = temp_path / "translated_audio.wav"
            if generate_translated_audio(
                str(translated_subtitle_path), 
                str(translated_audio_path), 
                target_lang_code
            ):
                progress_bar.progress(90)
                st.success("Translated audio generated!")
            else:
                st.error("Failed to generate translated audio")
                st.stop()
            
            # Step 7: Replace audio track
            status_text.text("🎬 Step 7: Creating final video...")
            output_video_path = temp_path / "dubbed_video.mp4"
            if replace_audio_track(
                str(video_path), 
                str(translated_audio_path), 
                str(output_video_path)
            ):
                progress_bar.progress(100)
                status_text.text("✅ Dubbing completed successfully!")
                
                # Display success message
                st.markdown('<div class="success-box">🎉 <strong>Dubbing Process Completed!</strong></div>', 
                           unsafe_allow_html=True)
                
                # Download section
                st.header("📥 Download Dubbed Video")
                
                # Read the final video file
                with open(output_video_path, "rb") as file:
                    video_bytes = file.read()
                
                st.download_button(
                    label="Download Dubbed Video",
                    data=video_bytes,
                    file_name=f"dubbed_{uploaded_file.name}",
                    mime="video/mp4",
                    type="primary"
                )
                
                # Show file info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Original File", uploaded_file.name)
                with col2:
                    st.metric("Source Language", source_lang)
                with col3:
                    st.metric("Dubbed Language", target_lang)
                
            else:
                st.error("Failed to create final video")
    
    else:
        st.warning("Please upload a video file first!")

# Instructions section
with st.expander("📖 How to Use This App"):
    st.markdown("""
    ### Step-by-Step Guide:
    
    1. **Upload Video**: Select your video file (MP4, AVI, MOV, MKV, WMV)
    2. **Select Languages**: 
       - Choose the original language of your video
       - Choose the target language for dubbing
    3. **Start Processing**: Click the "Start Dubbing Process" button
    4. **Wait**: The app will automatically process your video through all steps
    5. **Download**: Get your dubbed video when processing completes
    
    ### Processing Steps:
    - 🎵 Extract audio from video
    - 📝 Transcribe audio to text
    - 📄 Generate subtitles
    - 🌐 Translate subtitles
    - 🎙️ Generate translated audio
    - 🎬 Create final dubbed video
    
    ### Supported Languages:
    - **European**: English, Spanish, French, German, Italian, Portuguese, Russian
    - **Indian**: Hindi, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, Gujarati, Punjabi, Urdu
    - **Asian**: Chinese, Japanese, Korean, Arabic
    """)

# Technical details
with st.expander("🔧 Technical Information"):
    st.markdown("""
    ### Technologies Used:
    - **Speech Recognition**: Faster-Whisper (Offline)
    - **Translation**: Python Translate Library (Offline)
    - **Text-to-Speech**: gTTS (Google Text-to-Speech)
    - **Audio Processing**: PyDub, FFmpeg
    - **Video Processing**: MoviePy
    
    ### Features:
    - ✅ No external API keys required
    - ✅ Works entirely on mobile
    - ✅ Offline speech recognition
    - ✅ Multiple language support
    - ✅ Automatic timing preservation
    - ✅ Professional-quality output
    
    ### Note:
    - First run may take longer due to model downloads
    - Processing time depends on video length and model size
    - Internet required only for gTTS (text-to-speech)
    """)

# Footer
st.markdown("---")
st.markdown(
    "**Audio Dubbing App** • Built with Streamlit • "
    "No API Keys Required • Works Entirely on Mobile 📱"
)
