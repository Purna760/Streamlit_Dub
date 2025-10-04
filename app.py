import streamlit as st
import os
import tempfile
import math
import time
import io
import base64
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
    """Install required packages without ffmpeg dependencies"""
    import subprocess
    import sys
    
    packages = [
        "faster-whisper",
        "translate",
        "gtts",
        "pysrt",
        "pyaudio"  # Alternative audio processing
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
        model = WhisperModel("base")
        
        st.info("Transcribing audio...")
        segments, info = model.transcribe(audio_path)
        
        language = info.language
        language_probability = getattr(info, 'language_probability', 'N/A')
        
        st.success(f"Detected language: {language} (confidence: {language_probability})")
        
        segments = list(segments)
        st.write(f"Found {len(segments)} segments")
        
        # Display first few segments for verification
        with st.expander("Preview Transcription Segments"):
            for i, segment in enumerate(segments[:3]):
                st.write(f"**Segment {i+1}:** {segment.text}")
                st.write(f"Time: {segment.start:.2f}s - {segment.end:.2f}s")
                st.write("---")
        
        return language, segments
        
    except Exception as e:
        st.error(f"Transcription error: {str(e)}")
        st.info("Try using a different audio file or check the audio format.")
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
        
        st.success(f"Subtitles generated with {len(segments)} segments")
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
        
        translated_count = 0
        for i, sub in enumerate(subs):
            try:
                translated_text = translator.translate(sub.text)
                if translated_text:
                    sub.text = translated_text
                    translated_count += 1
                progress = (i + 1) / len(subs)
                progress_bar.progress(progress)
                status_text.text(f"Translating segment {i+1}/{len(subs)}")
            except Exception as e:
                st.warning(f"Could not translate segment {i+1}: {str(e)}")
                continue
        
        subs.save(translated_subtitle_path, encoding='utf-8')
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"Translated {translated_count}/{len(subs)} segments successfully")
        return True
        
    except Exception as e:
        st.error(f"Translation error: {str(e)}")
        return False

def generate_individual_audio_files(translated_subtitle_path, temp_dir, target_lang):
    """Generate individual audio files for each segment using gTTS"""
    try:
        import pysrt
        from gtts import gTTS
        
        st.info("Generating audio segments...")
        
        subs = pysrt.open(translated_subtitle_path)
        audio_files = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        successful_segments = 0
        for i, sub in enumerate(subs):
            text = sub.text.strip()
            
            if text and len(text) > 1:
                try:
                    # Generate speech using gTTS
                    tts = gTTS(text=text, lang=target_lang, slow=False)
                    
                    # Save to individual file
                    audio_file_path = os.path.join(temp_dir, f"segment_{i}.mp3")
                    tts.save(audio_file_path)
                    
                    audio_files.append({
                        'path': audio_file_path,
                        'start_time': sub.start.ordinal / 1000.0,
                        'text': text
                    })
                    successful_segments += 1
                    
                except Exception as e:
                    st.warning(f"Could not generate audio for segment {i+1}: {str(e)}")
                    continue
            
            progress = (i + 1) / len(subs)
            progress_bar.progress(progress)
            status_text.text(f"Generating audio segment {i+1}/{len(subs)}")
        
        progress_bar.empty()
        status_text.empty()
        
        st.success(f"Generated {successful_segments} audio segments")
        return audio_files
        
    except Exception as e:
        st.error(f"Audio segment generation error: {str(e)}")
        return []

def create_audio_download_page(audio_files, target_lang):
    """Create a download page for individual audio files"""
    st.header("🎵 Generated Audio Segments")
    st.info("Since we cannot combine audio without FFmpeg, here are the individual audio segments. You can download them and combine using any audio editing software.")
    
    for i, audio_file in enumerate(audio_files):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.write(f"**Segment {i+1}:** {audio_file['text']}")
            st.write(f"Start time: {audio_file['start_time']:.2f}s")
        
        with col2:
            # Play button
            with open(audio_file['path'], "rb") as f:
                audio_bytes = f.read()
            st.audio(audio_bytes, format='audio/mp3')
        
        with col3:
            # Download button
            with open(audio_file['path'], "rb") as f:
                st.download_button(
                    label="📥 Download",
                    data=f,
                    file_name=f"segment_{i+1}_{target_lang}.mp3",
                    mime="audio/mp3",
                    key=f"download_{i}"
                )
    
    # Provide instructions for combining
    st.markdown("---")
    st.subheader("🔧 How to Combine Audio Segments")
    st.markdown("""
    You can combine these audio segments using:
    
    - **Audacity** (Free, cross-platform)
    - **Online audio mergers** (search "online audio combiner")
    - **FFmpeg** (command line tool)
    - **Any audio editing software**
    
    **Simple FFmpeg command to combine:**
    ```bash
    ffmpeg -i "concat:segment1.mp3|segment2.mp3|segment3.mp3" -c copy output.mp3
    ```
    """)

def generate_combined_audio_alternative(audio_files, output_path):
    """Alternative method to combine audio using pure Python (limited)"""
    try:
        # This is a simplified approach that might work for some cases
        st.info("Attempting to combine audio segments...")
        
        # Since we can't use pydub without ffmpeg, we'll provide individual files
        # and instructions for manual combination
        return False
        
    except Exception as e:
        st.warning(f"Automatic combination not available: {str(e)}")
        return False

def main():
    # Sidebar
    st.sidebar.header("🎛️ Configuration")
    
    # Language selection
    st.sidebar.markdown("### Language Settings")
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
        "Choose an audio file", 
        type=['mp3', 'wav', 'm4a'],
        help="Upload an audio file to dub (MP3 recommended)"
    )
    
    if uploaded_file is not None:
        # Display file info
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)  # MB
        st.success(f"File uploaded: {uploaded_file.name} ({file_size:.2f} MB)")
        st.audio(uploaded_file, format='audio/mp3')
        
        # Show processing steps
        st.markdown("### 🔄 Processing Steps")
        steps = st.empty()
        
        # Dubbing button
        if st.button("🎙️ Start Audio Dubbing", type="primary"):
            steps.markdown("""
            1. ✅ **File Uploaded**
            2. 🔄 **Setting up environment...**
            3. ⏳ Transcribing Audio
            4. ⏳ Translating Text
            5. ⏳ Generating Audio Segments
            """)
            
            # Install packages
            with st.spinner("Setting up environment (this may take a minute)..."):
                install_packages()
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Step 1: Save uploaded file
                    input_audio_path = os.path.join(temp_dir, "input_audio.mp3")
                    with open(input_audio_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Step 2: Transcribe audio
                    steps.markdown("""
                    1. ✅ **File Uploaded**
                    2. ✅ **Environment Setup Complete**
                    3. ✅ **Transcribing Audio...**
                    4. 🔄 Translating Text
                    5. ⏳ Generating Audio Segments
                    """)
                    
                    source_lang_code, segments = transcribe_audio(input_audio_path)
                    
                    if segments is None or len(segments) == 0:
                        st.error("Transcription failed or no speech detected. Please try again with a different audio file.")
                        return
                    
                    # Step 3: Generate original subtitles
                    original_subtitle_path = os.path.join(temp_dir, "original_subtitles.srt")
                    if not generate_subtitle_file(segments, original_subtitle_path):
                        return
                    
                    # Step 4: Translate subtitles
                    steps.markdown("""
                    1. ✅ **File Uploaded**
                    2. ✅ **Environment Setup Complete**
                    3. ✅ **Transcribing Audio**
                    4. ✅ **Translating Text...**
                    5. 🔄 Generating Audio Segments
                    """)
                    
                    translated_subtitle_path = os.path.join(temp_dir, "translated_subtitles.srt")
                    
                    if not translate_subtitles(
                        original_subtitle_path, 
                        translated_subtitle_path, 
                        LANGUAGE_MAPPING[target_lang],
                        source_lang_code
                    ):
                        return
                    
                    # Step 5: Generate individual audio files
                    steps.markdown("""
                    1. ✅ **File Uploaded**
                    2. ✅ **Environment Setup Complete**
                    3. ✅ **Transcribing Audio**
                    4. ✅ **Translating Text**
                    5. ✅ **Generating Audio Segments...**
                    """)
                    
                    audio_files = generate_individual_audio_files(
                        translated_subtitle_path,
                        temp_dir,
                        LANGUAGE_MAPPING[target_lang]
                    )
                    
                    if not audio_files:
                        st.error("Failed to generate audio segments. Please try again.")
                        return
                    
                    # Step 6: Create download page
                    steps.markdown("""
                    1. ✅ **File Uploaded**
                    2. ✅ **Environment Setup Complete**
                    3. ✅ **Transcribing Audio**
                    4. ✅ **Translating Text**
                    5. ✅ **Generating Audio Segments**
                    """)
                    
                    create_audio_download_page(audio_files, target_lang)
                    
                    # Show processing summary
                    st.markdown("---")
                    st.subheader("📊 Processing Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Segments Processed", len(segments))
                    with col2:
                        st.metric("Audio Segments", len(audio_files))
                    with col3:
                        st.metric("Source Language", source_lang_code)
                    with col4:
                        st.metric("Target Language", target_lang)
                        
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")
                    st.info("""
                    **Troubleshooting tips:**
                    - Try a shorter audio file (under 1 minute)
                    - Ensure the audio has clear speech
                    - Check your internet connection
                    - Try MP3 format instead of WAV
                    """)

    else:
        # Instructions
        st.markdown("""
        ### 🚀 How to use this app:
        
        1. **Upload** an audio file (MP3, WAV, M4A)
        2. **Select** source and target languages
        3. **Click** "Start Audio Dubbing"
        4. **Wait** for processing to complete
        5. **Download** individual audio segments
        6. **Combine** segments using audio software
        
        ### 📋 Supported Features:
        
        - 🎵 **Audio file upload** (MP3, WAV, M4A)
        - 🌐 **20+ language support**
        - ⚡ **Local processing** (no API keys required)
        - 🎙️ **High-quality text-to-speech**
        - 📝 **Individual segment downloads**
        
        ### ⚠️ Important Notes:
        
        - First run may take longer to download models
        - Audio segments are provided separately (no FFmpeg dependency)
        - You'll need to combine segments manually
        - Use online tools or Audacity to combine audio files
        """)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Audio Dubbing App** • Built with Streamlit • "
        "No API keys required • No FFmpeg dependency"
    )

if __name__ == "__main__":
    main()
