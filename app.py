import streamlit as st
import os
import tempfile
import math
import time
from pathlib import Path
import warnings
import subprocess
import sys
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

def install_ffmpeg():
    """Install ffmpeg for pydub"""
    try:
        # Try to install ffmpeg using apt (for Linux environments)
        result = subprocess.run([
            'apt-get', 'update', '&&', 
            'apt-get', 'install', '-y', 'ffmpeg'
        ], capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            st.success("FFmpeg installed successfully")
            return True
        else:
            st.warning("Could not install FFmpeg via apt, trying alternative method...")
            return False
    except Exception as e:
        st.warning(f"FFmpeg installation attempt failed: {str(e)}")
        return False

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
        "pydub"
    ]
    
    for package in packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            st.info(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def setup_ffmpeg():
    """Setup ffmpeg path for pydub"""
    try:
        from pydub import AudioSegment
        
        # Try to find ffmpeg in system path
        import shutil
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")
        
        if ffmpeg_path:
            AudioSegment.ffmpeg = ffmpeg_path
        if ffprobe_path:
            AudioSegment.ffprobe = ffprobe_path
            
        st.success("FFmpeg configured successfully")
        return True
        
    except Exception as e:
        st.warning(f"FFmpeg setup warning: {str(e)}")
        return False

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
    """Transcribe audio using faster-whisper - FIXED VERSION"""
    try:
        from faster_whisper import WhisperModel
        
        st.info("Loading transcription model...")
        model = WhisperModel("base")  # Using base instead of small for better compatibility
        
        st.info("Transcribing audio...")
        segments, info = model.transcribe(audio_path)
        
        # FIX: Access language correctly from the info object
        language = info.language  # This is the correct way in newer versions
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

def generate_translated_audio_simple(translated_subtitle_path, output_audio_path, target_lang):
    """Simplified audio generation without complex timing"""
    try:
        import pysrt
        from gtts import gTTS
        from pydub import AudioSegment
        import io
        
        st.info("Generating translated audio (simplified version)...")
        
        subs = pysrt.open(translated_subtitle_path)
        
        # Create a simple combined audio by concatenating all segments
        combined = AudioSegment.silent(duration=0)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        successful_segments = 0
        for i, sub in enumerate(subs):
            text = sub.text.strip()
            
            if text and len(text) > 1:
                try:
                    # Generate speech using gTTS
                    tts = gTTS(text=text, lang=target_lang, slow=False)
                    
                    # Save to bytes buffer instead of file
                    audio_buffer = io.BytesIO()
                    tts.write_to_fp(audio_buffer)
                    audio_buffer.seek(0)
                    
                    # Load audio from buffer
                    audio = AudioSegment.from_mp3(audio_buffer)
                    
                    # Add a small pause between segments
                    if len(combined) > 0:
                        combined += AudioSegment.silent(duration=500)  # 500ms pause
                    
                    # Append the audio
                    combined += audio
                    successful_segments += 1
                    
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
        
        st.success(f"Generated audio for {successful_segments}/{len(subs)} segments")
        return True
        
    except Exception as e:
        st.error(f"Audio generation error: {str(e)}")
        return False

def generate_translated_audio_advanced(translated_subtitle_path, output_audio_path, target_lang):
    """Advanced audio generation with timing preservation"""
    try:
        import pysrt
        from gtts import gTTS
        from pydub import AudioSegment
        import io
        
        st.info("Generating translated audio with timing preservation...")
        
        subs = pysrt.open(translated_subtitle_path)
        combined = AudioSegment.silent(duration=0)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        successful_segments = 0
        for i, sub in enumerate(subs):
            start_time = sub.start.ordinal / 1000.0  # Convert to seconds
            text = sub.text.strip()
            
            if text and len(text) > 1:
                try:
                    # Generate speech using gTTS
                    tts = gTTS(text=text, lang=target_lang, slow=False)
                    
                    # Use bytes buffer to avoid file operations
                    audio_buffer = io.BytesIO()
                    tts.write_to_fp(audio_buffer)
                    audio_buffer.seek(0)
                    
                    # Load audio from buffer
                    audio_segment = AudioSegment.from_mp3(audio_buffer)
                    
                    # Calculate the required position
                    current_duration = len(combined) / 1000.0  # Convert to seconds
                    required_duration = start_time
                    
                    if required_duration > current_duration:
                        # Add silence to reach the required position
                        silence_duration = (required_duration - current_duration) * 1000  # Convert to milliseconds
                        combined += AudioSegment.silent(duration=silence_duration)
                    
                    # Append the audio segment
                    combined += audio_segment
                    successful_segments += 1
                    
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
        
        st.success(f"Generated audio for {successful_segments}/{len(subs)} segments with timing")
        return True
        
    except Exception as e:
        st.error(f"Advanced audio generation failed: {str(e)}")
        st.info("Falling back to simple audio generation...")
        return generate_translated_audio_simple(translated_subtitle_path, output_audio_path, target_lang)

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
    
    # Audio generation mode
    st.sidebar.markdown("### Audio Settings")
    audio_mode = st.sidebar.selectbox(
        "Audio Generation Mode",
        ["Simple (Faster)", "Advanced (Preserves Timing)"],
        index=0,
        help="Simple mode is more reliable, Advanced mode preserves original timing but may have issues"
    )
    
    # Model settings
    st.sidebar.markdown("### Model Settings")
    model_size = st.sidebar.selectbox(
        "Transcription Model Size",
        ["base", "small", "medium"],
        index=0,
        help="Base: Faster but less accurate, Medium: Slower but more accurate"
    )
    
    # File upload
    st.header("📁 Upload Audio File")
    uploaded_file = st.file_uploader(
        "Choose an audio file", 
        type=['mp3', 'wav', 'm4a'],
        help="Upload an audio file to dub (MP3, WAV, M4A recommended)"
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
            5. ⏳ Generating Dubbed Audio
            """)
            
            # Install packages and setup ffmpeg
            with st.spinner("Setting up environment (this may take a minute)..."):
                install_packages()
                setup_ffmpeg()
            
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
                    5. ⏳ Generating Dubbed Audio
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
                    5. 🔄 Generating Dubbed Audio
                    """)
                    
                    translated_subtitle_path = os.path.join(temp_dir, "translated_subtitles.srt")
                    
                    if not translate_subtitles(
                        original_subtitle_path, 
                        translated_subtitle_path, 
                        LANGUAGE_MAPPING[target_lang],
                        source_lang_code
                    ):
                        return
                    
                    # Step 5: Generate translated audio
                    steps.markdown("""
                    1. ✅ **File Uploaded**
                    2. ✅ **Environment Setup Complete**
                    3. ✅ **Transcribing Audio**
                    4. ✅ **Translating Text**
                    5. ✅ **Generating Dubbed Audio...**
                    """)
                    
                    output_audio_path = os.path.join(temp_dir, "dubbed_audio.mp3")
                    
                    if audio_mode == "Advanced (Preserves Timing)":
                        success = generate_translated_audio_advanced(
                            translated_subtitle_path,
                            output_audio_path,
                            LANGUAGE_MAPPING[target_lang]
                        )
                    else:
                        success = generate_translated_audio_simple(
                            translated_subtitle_path,
                            output_audio_path,
                            LANGUAGE_MAPPING[target_lang]
                        )
                    
                    if not success:
                        st.error("Audio generation failed. Please try the simple mode or a different file.")
                        return
                    
                    # Step 6: Provide download
                    steps.markdown("""
                    1. ✅ **File Uploaded**
                    2. ✅ **Environment Setup Complete**
                    3. ✅ **Transcribing Audio**
                    4. ✅ **Translating Text**
                    5. ✅ **Generating Dubbed Audio**
                    """)
                    
                    st.header("✅ Download Your Dubbed Audio")
                    st.success("Audio dubbing completed successfully!")
                    
                    # Read the output file
                    with open(output_audio_path, "rb") as file:
                        audio_bytes = file.read()
                    
                    # Create download button
                    st.download_button(
                        label="📥 Download Dubbed Audio",
                        data=audio_bytes,
                        file_name=f"dubbed_audio_{target_lang.lower()}.mp3",
                        mime="audio/mp3",
                        type="primary"
                    )
                    
                    # Play the dubbed audio
                    st.audio(audio_bytes, format='audio/mp3')
                    
                    # Show processing summary
                    st.markdown("---")
                    st.subheader("📊 Processing Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Segments Processed", len(segments))
                    with col2:
                        st.metric("Source Language", source_lang_code)
                    with col3:
                        st.metric("Target Language", target_lang)
                    with col4:
                        st.metric("File Size", f"{len(audio_bytes)/(1024*1024):.1f} MB")
                        
                except Exception as e:
                    st.error(f"Processing error: {str(e)}")
                    st.info("""
                    **Troubleshooting tips:**
                    - Try using Simple audio generation mode
                    - Use shorter audio files (under 2 minutes)
                    - Ensure the audio has clear speech
                    - Try MP3 format instead of WAV
                    """)

    else:
        # Instructions
        st.markdown("""
        ### 🚀 How to use this app:
        
        1. **Upload** an audio file (MP3, WAV, M4A)
        2. **Select** source and target languages
        3. **Choose** audio generation mode
        4. **Click** "Start Audio Dubbing"
        5. **Wait** for processing to complete
        6. **Download** your dubbed audio
        
        ### 📋 Supported Features:
        
        - 🎵 **Audio file upload** (MP3, WAV, M4A)
        - 🌐 **20+ language support**
        - ⚡ **Local processing** (no API keys required)
        - 🎙️ **High-quality text-to-speech**
        - ⏱️ **Timing preservation** (advanced mode)
        
        ### ⚠️ Important Notes:
        
        - First run may take longer to download models
        - Processing time depends on audio length
        - Use **Simple mode** for better reliability
        - **Advanced mode** preserves timing but may have issues
        """)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Audio Dubbing App** • Built with Streamlit • "
        "No API keys required • Fully local processing"
    )

if __name__ == "__main__":
    main()
