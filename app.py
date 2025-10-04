import streamlit as st
import os
import tempfile
import math
import time
from pathlib import Path
import subprocess
import base64
import requests

# Try to import required packages with error handling
try:
    import ffmpeg
except ImportError:
    st.error("ffmpeg-python not installed. Please check requirements.")

try:
    from faster_whisper import WhisperModel
except ImportError:
    st.error("faster-whisper not installed. Please check requirements.")

try:
    from translate import Translator
except ImportError:
    st.error("translate not installed. Please check requirements.")

try:
    import pysrt
except ImportError:
    st.error("pysrt not installed. Please check requirements.")

try:
    from gtts import gTTS
except ImportError:
    st.error("gTTS not installed. Please check requirements.")

try:
    from pydub import AudioSegment
except ImportError:
    st.error("pydub not installed. Please check requirements.")

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
    .progress-bar {
        width: 100%;
        background-color: #f0f0f0;
        border-radius: 10px;
        margin: 10px 0;
    }
    .progress-fill {
        height: 20px;
        background-color: #4CAF50;
        border-radius: 10px;
        text-align: center;
        color: white;
        line-height: 20px;
    }
</style>
""", unsafe_allow_html=True)

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
if 'current_step' not in st.session_state:
    st.session_state.current_step = 0
if 'total_steps' not in st.session_state:
    st.session_state.total_steps = 6

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
    """Get video duration using ffprobe"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 
            'format=duration', '-of', 
            'default=noprint_wrappers=1:nokey=1', video_path
        ], capture_output=True, text=True)
        return float(result.stdout)
    except:
        return 0

def extract_audio(video_path, audio_path):
    """Extract audio from video using ffmpeg"""
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path, '-q:a', '0', 
            '-map', 'a', audio_path, '-y'
        ], capture_output=True, check=True)
        return True
    except Exception as e:
        st.error(f"Error extracting audio: {e}")
        return False

def transcribe_audio(audio_path):
    """Transcribe audio using Whisper"""
    try:
        model = WhisperModel("base")  # Using base for faster processing
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
        
        for i, sub in enumerate(subs):
            try:
                # Add delay to avoid rate limiting
                if i % 5 == 0:
                    time.sleep(0.1)
                sub.text = translator.translate(sub.text)
            except Exception as e:
                st.warning(f"Could not translate line {i+1}: {e}")
                continue
        
        subs.save(translated_subtitle_path, encoding='utf-8')
        return True
    except Exception as e:
        st.error(f"Error translating subtitles: {e}")
        return False

def generate_translated_audio(translated_subtitle_path, output_audio_path, target_lang):
    """Generate audio for translated subtitles"""
    try:
        subs = pysrt.open(translated_subtitle_path)
        audio_segments = []
        
        for i, sub in enumerate(subs):
            start_time = sub.start.ordinal / 1000.0  # Convert to seconds
            text = sub.text.strip()
            
            if not text:
                continue
                
            try:
                # Generate speech using gTTS
                tts = gTTS(text=text, lang=target_lang, slow=False)
                temp_mp3 = f"temp_{i}.mp3"
                tts.save(temp_mp3)
                
                # Load audio and add timing info
                audio = AudioSegment.from_mp3(temp_mp3)
                audio_segments.append({
                    'start': start_time,
                    'audio': audio,
                    'duration': len(audio) / 1000.0  # Duration in seconds
                })
                
                # Clean up temp file
                os.unlink(temp_mp3)
                
                # Small delay to avoid rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                st.warning(f"Could not generate audio for line {i+1}: {e}")
                continue
        
        # Create final audio track
        if not audio_segments:
            st.error("No audio segments were generated")
            return False
            
        # Find total duration needed
        max_end_time = max(seg['start'] + seg['duration'] for seg in audio_segments)
        combined = AudioSegment.silent(duration=int(max_end_time * 1000))
        
        # Place audio segments at correct timings
        for seg in audio_segments:
            start_ms = int(seg['start'] * 1000)
            combined = combined.overlay(seg['audio'], position=start_ms)
        
        # Export final audio
        combined.export(output_audio_path, format="wav")
        return True
        
    except Exception as e:
        st.error(f"Error generating translated audio: {e}")
        return False

def replace_audio_track(video_path, audio_path, output_path):
    """Replace audio track in video using ffmpeg"""
    try:
        subprocess.run([
            'ffmpeg', '-i', video_path, '-i', audio_path,
            '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', output_path, '-y'
        ], capture_output=True, check=True)
        return True
    except Exception as e:
        st.error(f"Error replacing audio track: {e}")
        return False

def update_progress(step, total_steps, message):
    """Update progress bar"""
    progress = step / total_steps
    st.session_state.current_step = step
    return progress, message

# Main app interface
st.title("🎬 Video Dubbing App")
st.markdown("**Dub your videos into multiple languages automatically - No API keys required!**")

# Sidebar
st.sidebar.header("⚙️ Settings")

# File upload
uploaded_file = st.sidebar.file_uploader(
    "Upload Video File", 
    type=['mp4', 'avi', 'mov', 'mkv', 'webm'],
    help="Upload a video file to dub (max 50MB for best performance)"
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

# Processing info
st.sidebar.header("ℹ️ Processing Info")
st.sidebar.info("""
**Processing Steps:**
1. Extract audio from video
2. Transcribe audio to text
3. Generate subtitles
4. Translate subtitles
5. Generate new audio
6. Merge with video

**Note:** Longer videos take more time to process.
""")

# Main content area
if uploaded_file is not None:
    # Check file size
    if uploaded_file.size > 100 * 1024 * 1024:  # 100MB limit
        st.error("File size too large. Please upload a video smaller than 100MB.")
    else:
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
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                st.write(f"**Duration:** {minutes}m {seconds}s")
                st.write(f"**Source Language:** {source_lang_name}")
                st.write(f"**Target Language:** {target_lang_name}")
                
                # Estimate processing time
                estimated_time = duration * 2  # Rough estimate
                if estimated_time > 60:
                    st.warning(f"⏰ Estimated processing time: {estimated_time/60:.1f} minutes")
                else:
                    st.info(f"⏰ Estimated processing time: {estimated_time:.0f} seconds")

        # Process button
        if st.button("🎬 Start Dubbing Process", type="primary") and not st.session_state.processing:
            st.session_state.processing = True
            
            # Create progress trackers
            progress_bar = st.progress(0)
            status_text = st.empty()
            step_details = st.empty()
            
            try:
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_dir = Path(temp_dir)
                    
                    # Step 1: Extract audio
                    progress, message = update_progress(1, 6, "Extracting audio from video...")
                    progress_bar.progress(progress)
                    status_text.text(f"Step 1/6: {message}")
                    step_details.text("This may take a few seconds...")
                    
                    audio_path = temp_dir / "extracted_audio.wav"
                    if not extract_audio(video_path, str(audio_path)):
                        st.error("❌ Failed to extract audio from video")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 2: Transcribe audio
                    progress, message = update_progress(2, 6, "Transcribing audio to text...")
                    progress_bar.progress(progress)
                    status_text.text(f"Step 2/6: {message}")
                    step_details.text("Converting speech to text using Whisper...")
                    
                    language, segments = transcribe_audio(str(audio_path))
                    if not segments:
                        st.error("❌ Failed to transcribe audio. Please check if the video has clear audio.")
                        st.session_state.processing = False
                        st.stop()
                    
                    st.sidebar.success(f"Detected language: {language}")
                    
                    # Step 3: Generate original subtitles
                    progress, message = update_progress(3, 6, "Generating subtitles...")
                    progress_bar.progress(progress)
                    status_text.text(f"Step 3/6: {message}")
                    
                    subtitle_path = temp_dir / "original_subtitles.srt"
                    if not generate_subtitle_file(segments, str(subtitle_path)):
                        st.error("❌ Failed to generate subtitles")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 4: Translate subtitles
                    progress, message = update_progress(4, 6, "Translating subtitles...")
                    progress_bar.progress(progress)
                    status_text.text(f"Step 4/6: {message}")
                    step_details.text(f"Translating from {source_lang_name} to {target_lang_name}...")
                    
                    translated_subtitle_path = temp_dir / "translated_subtitles.srt"
                    if not translate_subtitles(str(subtitle_path), str(translated_subtitle_path), target_lang, source_lang):
                        st.error("❌ Failed to translate subtitles")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 5: Generate translated audio
                    progress, message = update_progress(5, 6, "Generating translated audio...")
                    progress_bar.progress(progress)
                    status_text.text(f"Step 5/6: {message}")
                    step_details.text("Creating new audio track with translated speech...")
                    
                    translated_audio_path = temp_dir / "translated_audio.wav"
                    if not generate_translated_audio(str(translated_subtitle_path), str(translated_audio_path), target_lang):
                        st.error("❌ Failed to generate translated audio")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 6: Replace audio track
                    progress, message = update_progress(6, 6, "Creating final video...")
                    progress_bar.progress(progress)
                    status_text.text(f"Step 6/6: {message}")
                    step_details.text("Merging new audio with original video...")
                    
                    output_path = temp_dir / "dubbed_video.mp4"
                    if not replace_audio_track(video_path, str(translated_audio_path), str(output_path)):
                        st.error("❌ Failed to create final video")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Read output file
                    with open(output_path, "rb") as f:
                        st.session_state.output_video = f.read()
                    
                    # Complete progress
                    progress_bar.progress(1.0)
                    status_text.text("✅ Processing Complete!")
                    step_details.text("Your dubbed video is ready for download!")
                    
                    st.balloons()
                
                st.session_state.processing = False
                
            except Exception as e:
                st.error(f"❌ Processing failed: {str(e)}")
                st.session_state.processing = False
                progress_bar.empty()
                status_text.text("❌ Processing Failed")
                step_details.text(f"Error: {str(e)}")

# Display results
if st.session_state.output_video is not None:
    st.header("🎉 Dubbing Complete!")
    
    # Create download link
    output_filename = f"dubbed_{target_lang}_{uploaded_file.name}"
    b64_video = base64.b64encode(st.session_state.output_video).decode()
    
    st.markdown(f"""
    <div class="success-box">
        <h4>✅ Success!</h4>
        <p>Your video has been successfully dubbed from <strong>{source_lang_name}</strong> to <strong>{target_lang_name}</strong>.</p>
        <p>Click the download button below to get your dubbed video.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.download_button(
        label="📥 Download Dubbed Video",
        data=st.session_state.output_video,
        file_name=output_filename,
        mime="video/mp4",
        use_container_width=True
    )
    
    # Option to process another video
    if st.button("🔄 Process Another Video", use_container_width=True):
        st.session_state.output_video = None
        st.session_state.processing = False
        st.rerun()

# Instructions section
else:
    st.header("📋 How to Use")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("1. Upload Video")
        st.write("• Click 'Browse files' in sidebar")
        st.write("• Select your video file")
        st.write("• Supported formats: MP4, AVI, MOV, MKV")
        st.write("• Max size: 100MB")
    
    with col2:
        st.subheader("2. Configure Languages")
        st.write("• Select original video language")
        st.write("• Choose target dubbing language")
        st.write("• 17+ languages supported")
        st.write("• Uses free translation services")
    
    with col3:
        st.subheader("3. Process & Download")
        st.write("• Click 'Start Dubbing Process'")
        st.write("• Wait for automatic processing")
        st.write("• Download your dubbed video")
        st.write("• No signup or API keys needed")

# Requirements information
st.sidebar.markdown("---")
st.sidebar.header("🔧 Technical Info")
st.sidebar.markdown("""
**Technologies Used:**
- Faster-Whisper (Speech-to-Text)
- Google Translate (Translation)
- gTTS (Text-to-Speech)
- FFmpeg (Video Processing)
""")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center'><p>🎬 <strong>Video Dubbing App</strong> • ⚡ <strong>No API Keys Required</strong> • 📱 <strong>Mobile Friendly</strong></p></div>",
    unsafe_allow_html=True
)

# Clean up temporary files
try:
    if 'video_path' in locals() and os.path.exists(video_path):
        os.unlink(video_path)
except:
    pass
