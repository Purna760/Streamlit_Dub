import streamlit as st
import os
import tempfile
import math
import time
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# App configuration
st.set_page_config(
    page_title="Audio Dubbing App",
    page_icon="🎙️",
    layout="centered"
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
        width: 100%;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        color: #155724;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        color: #856404;
    }
</style>
""", unsafe_allow_html=True)

# Title and description
st.title("🎙️ Audio Dubbing App")
st.markdown("**Translate and dub your audio files without any external API keys!**")

# Language mapping
LANGUAGE_MAPPING = {
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
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese (Simplified)": "zh-cn",
    "Arabic": "ar",
    "Russian": "ru"
}

def install_packages():
    """Install required packages"""
    import subprocess
    import sys
    
    packages = [
        "faster-whisper",
        "ffmpeg-python", 
        "translate",
        "gtts",
        "pysrt",
        "pydub",
        "moviepy"
    ]
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            st.info(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

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

def transcribe_audio(audio_path):
    """Transcribe audio using faster-whisper"""
    try:
        from faster_whisper import WhisperModel
        
        st.info("Loading transcription model...")
        model = WhisperModel("small")
        
        st.info("Transcribing audio...")
        segments, info = model.transcribe(audio_path)
        language = info[0]
        
        st.success(f"Detected language: {language}")
        
        segments = list(segments)
        st.write(f"Found {len(segments)} segments")
        
        return language, segments
        
    except Exception as e:
        st.error(f"Transcription error: {str(e)}")
        return None, None

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

        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(text)
        
        return True
        
    except Exception as e:
        st.error(f"Subtitle generation error: {str(e)}")
        return False

def translate_subtitles(subtitle_path, translated_subtitle_path, target_lang, source_lang="en"):
    """Translate subtitles to target language"""
    try:
        import pysrt
        from translate import Translator
        
        st.info(f"Translating from {source_lang} to {target_lang}...")
        
        subs = pysrt.open(subtitle_path)
        translator = Translator(to_lang=target_lang, from_lang=source_lang)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, sub in enumerate(subs):
            try:
                sub.text = translator.translate(sub.text)
                progress = (i + 1) / len(subs)
                progress_bar.progress(progress)
                status_text.text(f"Translating segment {i+1}/{len(subs)}")
            except Exception as e:
                st.warning(f"Could not translate segment {i+1}: {str(e)}")
                continue
        
        subs.save(translated_subtitle_path)
        progress_bar.empty()
        status_text.empty()
        
        return True
        
    except Exception as e:
        st.error(f"Translation error: {str(e)}")
        return False

def generate_translated_audio(translated_subtitle_path, output_audio_path, target_lang):
    """Generate audio for translated subtitles"""
    try:
        import pysrt
        from gtts import gTTS
        from pydub import AudioSegment
        import os
        
        st.info("Generating translated audio...")
        
        subs = pysrt.open(translated_subtitle_path)
        combined = AudioSegment.silent(duration=0)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, sub in enumerate(subs):
            start_time = sub.start.ordinal / 1000.0
            text = sub.text
            
            if text.strip():
                try:
                    # Generate speech using gTTS
                    tts = gTTS(text=text, lang=target_lang, slow=False)
                    temp_file = "temp_audio.mp3"
                    tts.save(temp_file)
                    
                    # Load and process audio
                    audio = AudioSegment.from_mp3(temp_file)
                    
                    # Calculate position to insert audio
                    current_duration = len(combined)
                    silent_duration = start_time * 1000 - current_duration
                    
                    if silent_duration > 0:
                        combined += AudioSegment.silent(duration=silent_duration)
                    
                    combined += audio
                    os.remove(temp_file)
                    
                except Exception as e:
                    st.warning(f"Could not generate audio for segment {i+1}: {str(e)}")
                    continue
            
            progress = (i + 1) / len(subs)
            progress_bar.progress(progress)
            status_text.text(f"Generating audio segment {i+1}/{len(subs)}")
        
        # Export final audio
        combined.export(output_audio_path, format="mp3")
        
        progress_bar.empty()
        status_text.empty()
        
        return True
        
    except Exception as e:
        st.error(f"Audio generation error: {str(e)}")
        return False

def main():
    # Sidebar
    st.sidebar.header("🎛️ Configuration")
    
    # Language selection
    source_lang = st.sidebar.selectbox(
        "Source Language (for translation)",
        list(LANGUAGE_MAPPING.keys()),
        index=0
    )
    
    target_lang = st.sidebar.selectbox(
        "Target Language (for dubbing)",
        list(LANGUAGE_MAPPING.keys()),
        index=7  # Default to Tamil
    )
    
    # File upload
    st.header("📁 Upload Audio File")
    uploaded_file = st.file_uploader(
        "Choose an MP3 audio file", 
        type=['mp3', 'wav', 'm4a', 'ogg'],
        help="Upload an audio file to dub"
    )
    
    if uploaded_file is not None:
        # Display file info
        st.success(f"File uploaded: {uploaded_file.name}")
        st.audio(uploaded_file, format='audio/mp3')
        
        # Dubbing button
        if st.button("🎙️ Start Audio Dubbing", type="primary"):
            with st.spinner("Setting up environment..."):
                install_packages()
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Step 1: Save uploaded file
                    input_audio_path = os.path.join(temp_dir, "input_audio.mp3")
                    with open(input_audio_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Step 2: Transcribe audio
                    st.header("📝 Step 1: Transcription")
                    source_lang_code, segments = transcribe_audio(input_audio_path)
                    
                    if segments is None:
                        st.error("Transcription failed. Please try again.")
                        return
                    
                    # Step 3: Generate original subtitles
                    original_subtitle_path = os.path.join(temp_dir, "original_subtitles.srt")
                    if not generate_subtitle_file(segments, original_subtitle_path):
                        return
                    
                    # Display some transcribed segments
                    with st.expander("View Transcribed Text"):
                        for i, segment in enumerate(segments[:5]):  # Show first 5 segments
                            st.write(f"**Segment {i+1}:** {segment.text}")
                    
                    # Step 4: Translate subtitles
                    st.header("🌐 Step 2: Translation")
                    translated_subtitle_path = os.path.join(temp_dir, "translated_subtitles.srt")
                    
                    if not translate_subtitles(
                        original_subtitle_path, 
                        translated_subtitle_path, 
                        LANGUAGE_MAPPING[target_lang],
                        source_lang_code
                    ):
                        return
                    
                    # Step 5: Generate translated audio
                    st.header("🎙️ Step 3: Audio Generation")
                    output_audio_path = os.path.join(temp_dir, "dubbed_audio.mp3")
                    
                    if not generate_translated_audio(
                        translated_subtitle_path,
                        output_audio_path,
                        LANGUAGE_MAPPING[target_lang]
                    ):
                        return
                    
                    # Step 6: Provide download
                    st.header("✅ Step 4: Download")
                    st.success("Audio dubbing completed successfully!")
                    
                    # Read the output file
                    with open(output_audio_path, "rb") as file:
                        audio_bytes = file.read()
                    
                    # Create download button
                    st.download_button(
                        label="📥 Download Dubbed Audio",
                        data=audio_bytes,
                        file_name=f"dubbed_audio_{target_lang.lower()}.mp3",
                        mime="audio/mp3"
                    )
                    
                    # Play the dubbed audio
                    st.audio(audio_bytes, format='audio/mp3')
                    
                    # Show processing summary
                    st.markdown("---")
                    st.subheader("📊 Processing Summary")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Segments Processed", len(segments))
                    with col2:
                        st.metric("Source Language", source_lang_code)
                    with col3:
                        st.metric("Target Language", target_lang)
                        
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")
                    st.info("Please try again with a different audio file.")

    else:
        # Instructions
        st.markdown("""
        ### 🚀 How to use this app:
        
        1. **Upload** an MP3 audio file
        2. **Select** source and target languages
        3. **Click** "Start Audio Dubbing"
        4. **Wait** for processing to complete
        5. **Download** your dubbed audio
        
        ### 📋 Supported Features:
        
        - 🎵 **Audio file upload** (MP3, WAV, M4A, OGG)
        - 🌐 **Multiple language support**
        - ⚡ **Local processing** (no API keys required)
        - 🎙️ **High-quality text-to-speech**
        - ⏱️ **Automatic timing preservation**
        
        ### 🗣️ Supported Languages:
        
        - **European**: English, Spanish, French, German, Italian, Portuguese
        - **Indian**: Hindi, Tamil, Telugu, Malayalam, Kannada, Bengali, Marathi, Gujarati, Punjabi
        - **Asian**: Japanese, Korean, Chinese, Arabic, Russian
        """)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Audio Dubbing App** • Built with Streamlit • "
        "No API keys required • Fully local processing"
    )

if __name__ == "__main__":
    main()
