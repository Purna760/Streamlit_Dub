import streamlit as st
import tempfile
import os
import subprocess
import base64
from pathlib import Path

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
    .progress-bar {
        width: 100%;
        background-color: #f0f0f0;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Supported languages
LANGUAGES = {
    'English': 'en',
    'Spanish': 'es', 
    'French': 'fr',
    'German': 'de',
    'Hindi': 'hi',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Bengali': 'bn'
}

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'output_video' not in st.session_state:
    st.session_state.output_video = None

# Basic utility functions
def extract_audio_simple(video_path, audio_path):
    """Extract audio from video using ffmpeg"""
    try:
        cmd = [
            'ffmpeg', '-i', video_path, 
            '-vn', '-acodec', 'pcm_s16le', 
            '-ar', '16000', '-ac', '1', 
            audio_path, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        st.error(f"Audio extraction error: {e}")
        return False

def get_video_duration(video_path):
    """Get video duration using ffprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except:
        return 0

def create_dummy_audio(video_path, output_audio_path, language):
    """Create a simple test audio file"""
    try:
        # Extract original audio duration
        duration = get_video_duration(video_path)
        
        # Create a simple tone or use silence
        cmd = [
            'ffmpeg', '-f', 'lavfi', 
            '-i', f'sine=frequency=1000:duration={duration}',
            output_audio_path, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Fallback: copy original audio
            cmd = ['ffmpeg', '-i', video_path, '-map', '0:a:0', output_audio_path, '-y']
            subprocess.run(cmd, capture_output=True)
        
        return True
    except Exception as e:
        st.error(f"Audio creation error: {e}")
        return False

def replace_audio_track_simple(video_path, audio_path, output_path):
    """Replace audio track in video"""
    try:
        cmd = [
            'ffmpeg', '-i', video_path, '-i', audio_path,
            '-c:v', 'copy', '-c:a', 'aac',
            '-map', '0:v:0', '-map', '1:a:0',
            '-shortest', output_path, '-y'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        st.error(f"Audio replacement error: {e}")
        return False

# Main app interface
st.title("🎬 Video Dubbing App")
st.markdown("**Dub your videos into multiple languages automatically - No API keys required!**")

# Sidebar
st.sidebar.header("⚙️ Settings")

# File upload
uploaded_file = st.sidebar.file_uploader(
    "Upload Video File", 
    type=['mp4', 'avi', 'mov'],
    help="Upload a video file to dub"
)

# Language selection
col1, col2 = st.sidebar.columns(2)
with col1:
    source_lang_name = st.selectbox(
        "Source Language",
        options=list(LANGUAGES.keys()),
        index=0
    )

with col2:
    target_lang_name = st.selectbox(
        "Target Language", 
        options=list(LANGUAGES.keys()),
        index=5  # Tamil
    )

# Debug info
st.sidebar.header("🔧 Debug")
st.sidebar.info("Phase 1: Basic video processing")

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
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            st.write(f"**Duration:** {minutes}m {seconds}s")
            st.write(f"**Source:** {source_lang_name}")
            st.write(f"**Target:** {target_lang_name}")

    # Process button
    if st.button("🎬 Test Basic Processing", type="primary") and not st.session_state.processing:
        st.session_state.processing = True
        
        with st.status("🚀 Testing Basic Processing...", expanded=True) as status:
            try:
                # Create temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_dir = Path(temp_dir)
                    
                    # Step 1: Extract audio
                    status.update(label="1. Extracting audio...")
                    audio_path = temp_dir / "extracted_audio.wav"
                    if extract_audio_simple(video_path, str(audio_path)):
                        st.sidebar.success("✅ Audio extraction working")
                    else:
                        st.error("❌ Audio extraction failed")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 2: Create test audio (simulating translation)
                    status.update(label="2. Creating test audio...")
                    test_audio_path = temp_dir / "test_audio.wav"
                    if create_dummy_audio(video_path, str(test_audio_path), target_lang_name):
                        st.sidebar.success("✅ Audio creation working")
                    else:
                        st.error("❌ Audio creation failed")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Step 3: Replace audio track
                    status.update(label="3. Merging audio with video...")
                    output_path = temp_dir / "output_video.mp4"
                    if replace_audio_track_simple(video_path, str(test_audio_path), str(output_path)):
                        st.sidebar.success("✅ Video merging working")
                    else:
                        st.error("❌ Video merging failed")
                        st.session_state.processing = False
                        st.stop()
                    
                    # Read output file
                    with open(output_path, "rb") as f:
                        st.session_state.output_video = f.read()
                    
                    status.update(label="✅ Basic Processing Complete!", state="complete")
                
                st.session_state.processing = False
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Processing failed: {str(e)}")
                st.session_state.processing = False

# Display results
if st.session_state.output_video is not None:
    st.header("🎉 Basic Processing Complete!")
    
    # Create download link
    output_filename = f"processed_{uploaded_file.name}"
    
    st.markdown(f"""
    <div class="success-box">
        <h4>✅ Success!</h4>
        <p>Basic video processing is working correctly.</p>
        <p>The app can:</p>
        <ul>
            <li>✅ Extract audio from video</li>
            <li>✅ Process audio files</li>
            <li>✅ Merge audio with video</li>
            <li>✅ Generate output files</li>
        </ul>
        <p>Next step: Add speech recognition and translation.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.download_button(
        label="📥 Download Processed Video",
        data=st.session_state.output_video,
        file_name=output_filename,
        mime="video/mp4",
        use_container_width=True
    )

# Instructions
st.header("📋 Development Progress")
st.markdown("""
### Current Phase: Basic Video Processing ✅

**What's working:**
- Video upload and preview
- Audio extraction using FFmpeg
- Basic audio processing
- Video/audio merging
- File download

**Next Phase:**
- Add speech-to-text (Whisper)
- Add translation functionality
- Add text-to-speech (gTTS)

**Technical Stack:**
- Streamlit (UI)
- FFmpeg (Video processing)
- Python (Backend logic)
""")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center'><p>🎬 <strong>Video Dubbing App - Phase 1</strong> • ⚡ <strong>Basic Processing Working</strong></p></div>",
    unsafe_allow_html=True
)

# Cleanup
try:
    if 'video_path' in locals() and os.path.exists(video_path):
        os.unlink(video_path)
except:
    pass
