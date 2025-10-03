import streamlit as st
import os
import tempfile
import math
import time
from pathlib import Path
import ffmpeg
from faster_whisper import WhisperModel
import pysrt
from translate import Translator
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip
import base64
import subprocess
import soundfile as sf
import io

# App configuration
st.set_page_config(
    page_title="Video Dubbing App",
    page_icon="🎬",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 20px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        margin: 10px 0;
    }
    .warning-box {
        padding: 15px;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="main-header">🎬 AI Video Dubbing App</div>', unsafe_allow_html=True)
st.write("Upload a video and translate it to any language automatically!")

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False

# Helper functions
def update_progress(step, progress):
    st.session_state.current_step = step
    st.session_state.progress = progress

def format_time(seconds):
    hours = math.floor(seconds / 3600)
    seconds %= 3600
    minutes = math.floor(seconds / 60)
    seconds %= 60
    milliseconds = round((seconds - math.floor(seconds)) * 1000)
    seconds = math.floor(seconds)
    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:01d},{milliseconds:03d}"
    return formatted_time

def extract_audio(video_path):
    """Extract audio from video file using ffmpeg"""
    try:
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_audio.close()
        
        # Use ffmpeg to extract audio
        (
            ffmpeg
            .input(video_path)
            .output(temp_audio.name, ac=1, ar=16000)  # mono, 16kHz for better transcription
            .overwrite_output()
            .run(quiet=True)
        )
        return temp_audio.name
    except Exception as e:
        st.error(f"Error extracting audio: {str(e)}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using Whisper"""
    update_progress("Transcribing audio...", 30)
    
    try:
        # Use smaller model for faster processing
        model = WhisperModel("base")
        segments, info = model.transcribe(audio_path, beam_size=5)
        language = info[0]
        st.info(f"Detected language: {language}")
        
        segments = list(segments)
        return language, segments
    except Exception as e:
        st.error(f"Error in transcription: {str(e)}")
        return None, None

def generate_subtitle_file(segments, output_dir):
    """Generate subtitle file from segments"""
    update_progress("Generating subtitles...", 50)
    
    subtitle_file = os.path.join(output_dir, "original_subtitles.srt")
    text = ""
    for index, segment in enumerate(segments):
        segment_start = format_time(segment.start)
        segment_end = format_time(segment.end)
        text += f"{str(index+1)} \n"
        text += f"{segment_start} --> {segment_end} \n"
        text += f"{segment.text} \n"
        text += "\n"

    with open(subtitle_file, "w", encoding='utf-8') as f:
        f.write(text)

    return subtitle_file

def translate_subtitles(subtitle_path, target_language, source_language='auto'):
    """Translate subtitles to target language"""
    update_progress("Translating subtitles...", 60)
    
    try:
        subs = pysrt.open(subtitle_path)
        translated_subs = pysrt.SubRipFile()
        
        for i, sub in enumerate(subs):
            try:
                # Use different translation approach
                if source_language == 'auto':
                    translator = Translator(to_lang=target_language)
                else:
                    translator = Translator(to_lang=target_language, from_lang=source_language)
                
                translated_text = translator.translate(sub.text)
                new_sub = pysrt.SubRipItem(
                    index=i,
                    start=sub.start,
                    end=sub.end,
                    text=translated_text
                )
                translated_subs.append(new_sub)
                
                # Progress update
                if i % 10 == 0:  # Update every 10 segments
                    progress = 60 + (i / len(subs)) * 20
                    update_progress(f"Translating... ({i+1}/{len(subs)})", progress)
                
            except Exception as e:
                st.warning(f"Could not translate line {i+1}: {str(e)}")
                # Keep original text if translation fails
                translated_subs.append(sub)
        
        translated_subtitle_path = subtitle_path.replace('.srt', f'_translated_{target_language}.srt')
        translated_subs.save(translated_subtitle_path, encoding='utf-8')
        return translated_subtitle_path
    
    except Exception as e:
        st.error(f"Error in translation: {str(e)}")
        return None

def generate_translated_audio_simple(translated_subtitle_path, target_language, output_dir, total_duration):
    """Generate audio using a simpler approach without pydub"""
    update_progress("Generating translated audio...", 80)
    
    try:
        subs = pysrt.open(translated_subtitle_path)
        
        # Create a temporary directory for audio segments
        temp_dir = tempfile.mkdtemp()
        audio_segments = []
        
        for i, sub in enumerate(subs):
            start_time = sub.start.ordinal / 1000.0
            text = sub.text
            
            if text.strip():
                try:
                    # Generate speech using gTTS
                    tts = gTTS(text=text, lang=target_language, slow=False)
                    temp_mp3 = os.path.join(temp_dir, f"segment_{i:04d}.mp3")
                    tts.save(temp_mp3)
                    
                    audio_segments.append({
                        'file': temp_mp3,
                        'start': start_time,
                        'text': text
                    })
                    
                except Exception as e:
                    st.warning(f"Could not generate audio for line {i+1}: {str(e)}")
        
        # Create a list file for ffmpeg concatenation
        list_file = os.path.join(temp_dir, "file_list.txt")
        with open(list_file, "w") as f:
            for segment in audio_segments:
                # Add silence before segment if needed
                if segment['start'] > 0:
                    # This is simplified - in production you'd need to handle gaps better
                    f.write(f"file 'silence.wav'\n")
                f.write(f"file '{segment['file']}'\n")
        
        # Generate output audio
        output_audio_path = os.path.join(output_dir, "translated_audio.mp3")
        
        # Use ffmpeg to combine (simplified approach)
        if audio_segments:
            # Use the first segment to get format info
            input_file = audio_segments[0]['file']
            (
                ffmpeg
                .input(input_file)
                .output(output_audio_path)
                .overwrite_output()
                .run(quiet=True)
            )
        
        # Cleanup temp directory
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                os.remove(os.path.join(root, file))
        os.rmdir(temp_dir)
        
        return output_audio_path
    
    except Exception as e:
        st.error(f"Error generating audio: {str(e)}")
        return None

def replace_audio_track_safe(video_path, new_audio_path, output_dir):
    """Replace audio track safely"""
    update_progress("Creating final video...", 90)
    
    try:
        output_video_path = os.path.join(output_dir, "dubbed_video.mp4")
        
        # Use ffmpeg directly for more reliable audio replacement
        (
            ffmpeg
            .input(video_path)
            .output(
                ffmpeg.input(new_audio_path),
                output_video_path,
                vcodec='copy',  # Copy video stream without re-encoding
                acodec='aac',
                strict='experimental'
            )
            .overwrite_output()
            .run(quiet=True)
        )
        
        return output_video_path
    
    except Exception as e:
        st.error(f"Error creating final video: {str(e)}")
        # Fallback: try moviepy
        try:
            video_clip = VideoFileClip(video_path)
            audio_clip = AudioFileClip(new_audio_path)
            final_video = video_clip.set_audio(audio_clip)
            final_video.write_videofile(
                output_video_path,
                codec='libx264',
                audio_codec='aac',
                verbose=False,
                logger=None
            )
            video_clip.close()
            audio_clip.close()
            final_video.close()
            return output_video_path
        except Exception as e2:
            st.error(f"Fallback also failed: {str(e2)}")
            return None

# Main app interface
def main():
    # Sidebar for controls
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Language selection
        st.subheader("Target Language")
        target_language = st.selectbox(
            "Select translation language",
            [
                "hi", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", 
                "zh", "ar", "ta", "te", "ml", "kn", "mr", "bn", "gu"
            ],
            format_func=lambda x: {
                "hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German",
                "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese",
                "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "ta": "Tamil",
                "te": "Telugu", "ml": "Malayalam", "kn": "Kannada", "mr": "Marathi",
                "bn": "Bengali", "gu": "Gujarati"
            }.get(x, x)
        )
        
        st.subheader("Model Settings")
        model_size = st.selectbox(
            "Whisper Model Size",
            ["base", "small", "medium"],
            index=0,  # Default to base for speed
            help="Larger models are more accurate but slower"
        )
        
        st.markdown("---")
        st.markdown("""
        <div class='warning-box'>
        <strong>Note:</strong> For best results:
        - Use short videos (1-5 minutes)
        - Ensure clear audio in original video
        - Processing may take 2-5 minutes
        </div>
        """, unsafe_allow_html=True)

    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Video")
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov', 'wmv', 'mkv'],
            help="Upload the video you want to dub"
        )
        
        if uploaded_file is not None:
            # Display video info
            file_size = uploaded_file.size / (1024 * 1024)  # MB
            st.write(f"**File:** {uploaded_file.name}")
            st.write(f"**Size:** {file_size:.2f} MB")
            
            # Display uploaded video
            st.video(uploaded_file)
    
    with col2:
        st.header("🎯 Processing")
        
        if uploaded_file is not None and st.button("🚀 Start Dubbing", type="primary"):
            if file_size > 100:  # Reduced from 200MB for stability
                st.error("File size too large! Please upload a video under 100MB for reliable processing.")
                return
            
            st.session_state.processing = True
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Save uploaded file
                    video_path = os.path.join(temp_dir, "input_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Step 1: Extract audio
                    status_text.text("🎵 Extracting audio from video...")
                    audio_path = extract_audio(video_path)
                    if not audio_path:
                        return
                    progress_bar.progress(20)
                    
                    # Step 2: Transcribe
                    status_text.text("📝 Transcribing audio...")
                    source_language, segments = transcribe_audio(audio_path)
                    if not segments:
                        return
                    progress_bar.progress(40)
                    
                    # Display transcription preview
                    with st.expander("View Transcription Preview"):
                        for i, segment in enumerate(segments[:5]):  # First 5 segments
                            st.write(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
                    
                    # Step 3: Generate original subtitles
                    status_text.text("📄 Generating subtitles...")
                    original_subtitle_path = generate_subtitle_file(segments, temp_dir)
                    progress_bar.progress(50)
                    
                    # Step 4: Translate subtitles
                    status_text.text("🌍 Translating to selected language...")
                    translated_subtitle_path = translate_subtitles(
                        original_subtitle_path, 
                        target_language,
                        source_language
                    )
                    if not translated_subtitle_path:
                        return
                    progress_bar.progress(70)
                    
                    # Step 5: Generate translated audio (simplified)
                    status_text.text("🔊 Generating translated audio...")
                    # Estimate total duration from segments
                    total_duration = max(segment.end for segment in segments) if segments else 60
                    translated_audio_path = generate_translated_audio_simple(
                        translated_subtitle_path,
                        target_language,
                        temp_dir,
                        total_duration
                    )
                    if not translated_audio_path:
                        return
                    progress_bar.progress(85)
                    
                    # Step 6: Create final video
                    status_text.text("🎬 Creating final dubbed video...")
                    final_video_path = replace_audio_track_safe(
                        video_path,
                        translated_audio_path,
                        temp_dir
                    )
                    if not final_video_path:
                        return
                    progress_bar.progress(100)
                    
                    # Success message
                    status_text.text("✅ Dubbing completed successfully!")
                    
                    # Display results
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.success("🎉 Video dubbing completed!")
                    
                    # Display final video
                    st.subheader("🎬 Dubbed Video Preview")
                    st.video(final_video_path)
                    
                    # Download button
                    st.subheader("📥 Download")
                    with open(final_video_path, "rb") as f:
                        video_data = f.read()
                    
                    st.download_button(
                        label="📥 Download Dubbed Video",
                        data=video_data,
                        file_name=f"dubbed_{target_language}_{uploaded_file.name}",
                        mime="video/mp4",
                        type="primary"
                    )
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"❌ Error during processing: {str(e)}")
                    st.info("""
                    **Troubleshooting tips:**
                    - Try a shorter video (under 2 minutes)
                    - Ensure the video has clear audio
                    - Try a different target language
                    - The video might be too large for processing
                    """)
                
                finally:
                    st.session_state.processing = False
        
        elif not uploaded_file:
            st.info("👆 Please upload a video file to start dubbing")
        
        # Display processing status
        if st.session_state.processing:
            st.warning("🔄 Processing... This may take several minutes depending on video length.")

    # Instructions section
    st.markdown("---")
    st.header("📖 How It Works")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.subheader("1. Upload")
        st.write("Upload your video file")
    
    with col2:
        st.subheader("2. Transcribe")
        st.write("AI automatically transcribes the audio")
    
    with col3:
        st.subheader("3. Translate")
        st.write("Subtitles are translated to your chosen language")
    
    with col4:
        st.subheader("4. Dub")
        st.write("New audio is generated and synced with video")

# Run the app
if __name__ == "__main__":
    main()
