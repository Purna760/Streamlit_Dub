import streamlit as st
import os
import tempfile
import math
import time
import ffmpeg
from faster_whisper import WhisperModel
import pysrt
from translate import Translator
from gtts import gTTS
import base64
import subprocess

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
    .info-box {
        padding: 15px;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
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
            .output(temp_audio.name, ac=1, ar=16000)
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
        return temp_audio.name
    except Exception as e:
        st.error(f"Error extracting audio: {str(e)}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using Whisper"""
    try:
        # Use base model for faster processing
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
    try:
        subs = pysrt.open(subtitle_path)
        translated_subs = pysrt.SubRipFile()
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, sub in enumerate(subs):
            try:
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
                
                # Update progress
                progress = (i + 1) / len(subs)
                progress_bar.progress(progress)
                status_text.text(f"Translating... {i+1}/{len(subs)}")
                
            except Exception as e:
                st.warning(f"Could not translate line {i+1}: {str(e)}")
                translated_subs.append(sub)
        
        translated_subtitle_path = subtitle_path.replace('.srt', f'_translated_{target_language}.srt')
        translated_subs.save(translated_subtitle_path, encoding='utf-8')
        status_text.text("Translation completed!")
        return translated_subtitle_path
    
    except Exception as e:
        st.error(f"Error in translation: {str(e)}")
        return None

def create_translated_audio_ffmpeg(translated_subtitle_path, target_language, output_dir, video_duration):
    """Create translated audio using ffmpeg only"""
    try:
        subs = pysrt.open(translated_subtitle_path)
        
        # Create a silent audio file of the same duration as video
        silent_audio = os.path.join(output_dir, "silent.wav")
        (
            ffmpeg
            .input('anullsrc', f='lavfi', t=video_duration)
            .output(silent_audio, ac=2, ar=44100)
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
        
        # For each subtitle, generate audio and mix it at the right time
        mixed_audio = silent_audio
        
        for i, sub in enumerate(subs):
            if i >= 10:  # Limit to first 10 segments for demo
                break
                
            text = sub.text.strip()
            if text:
                try:
                    # Generate TTS
                    tts = gTTS(text=text, lang=target_language, slow=False)
                    temp_audio = os.path.join(output_dir, f"tts_{i}.mp3")
                    tts.save(temp_audio)
                    
                    # Convert to WAV
                    temp_wav = os.path.join(output_dir, f"tts_{i}.wav")
                    (
                        ffmpeg
                        .input(temp_audio)
                        .output(temp_wav, ar=44100, ac=2)
                        .overwrite_output()
                        .run(quiet=True, capture_stdout=True, capture_stderr=True)
                    )
                    
                    # Mix with main audio at correct timestamp
                    start_time = sub.start.ordinal / 1000.0
                    mixed_output = os.path.join(output_dir, f"mixed_{i}.wav")
                    
                    # Use ffmpeg to mix audio at specific time
                    input1 = ffmpeg.input(mixed_audio)
                    input2 = ffmpeg.input(temp_wav).filter('adelay', f"{int(start_time * 1000)}|{int(start_time * 1000)}")
                    
                    (
                        ffmpeg
                        .filter([input1, input2], 'amix', inputs=2, duration='first')
                        .output(mixed_output)
                        .overwrite_output()
                        .run(quiet=True, capture_stdout=True, capture_stderr=True)
                    )
                    
                    mixed_audio = mixed_output
                    os.remove(temp_audio)
                    os.remove(temp_wav)
                    
                except Exception as e:
                    st.warning(f"Could not process audio for segment {i+1}: {str(e)}")
        
        final_audio = os.path.join(output_dir, "translated_audio.wav")
        os.rename(mixed_audio, final_audio)
        return final_audio
        
    except Exception as e:
        st.error(f"Error creating translated audio: {str(e)}")
        return None

def get_video_duration(video_path):
    """Get video duration using ffmpeg"""
    try:
        probe = ffmpeg.probe(video_path)
        video_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')
        duration = float(video_info['duration'])
        return duration
    except Exception as e:
        st.warning(f"Could not get video duration, using default: {str(e)}")
        return 60.0  # Default 1 minute

def replace_audio_ffmpeg(video_path, audio_path, output_dir):
    """Replace audio in video using ffmpeg"""
    try:
        output_video_path = os.path.join(output_dir, "dubbed_video.mp4")
        
        # Use ffmpeg to replace audio stream
        (
            ffmpeg
            .input(video_path)
            .output(
                ffmpeg.input(audio_path),
                output_video_path,
                vcodec='copy',  # Copy video without re-encoding
                acodec='aac',
                strict='experimental'
            )
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
        
        return output_video_path
        
    except Exception as e:
        st.error(f"Error replacing audio: {str(e)}")
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
                "zh", "ar", "ta", "te", "ml", "kn", "mr", "bn", "gu", "en"
            ],
            format_func=lambda x: {
                "hi": "Hindi", "es": "Spanish", "fr": "French", "de": "German",
                "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese",
                "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "ta": "Tamil",
                "te": "Telugu", "ml": "Malayalam", "kn": "Kannada", "mr": "Marathi",
                "bn": "Bengali", "gu": "Gujarati", "en": "English"
            }.get(x, x)
        )
        
        st.markdown("---")
        st.markdown("""
        <div class='info-box'>
        <strong>Tips for best results:</strong>
        - Use short videos (under 2 minutes)
        - Clear audio works best
        - Processing takes 2-5 minutes
        - First run downloads models (be patient)
        </div>
        """, unsafe_allow_html=True)

    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Video")
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'avi', 'mov', 'wmv'],
            help="For best results, use short videos with clear audio"
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
            if file_size > 50:  # 50MB limit for stability
                st.error("Please upload a video under 50MB for reliable processing.")
                return
            
            st.session_state.processing = True
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Save uploaded file
                    video_path = os.path.join(temp_dir, "input_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Main progress container
                    progress_container = st.container()
                    
                    with progress_container:
                        st.subheader("Processing Steps")
                        
                        # Step 1: Get video duration
                        st.write("📏 **Getting video duration...**")
                        video_duration = get_video_duration(video_path)
                        st.write(f"Video duration: {video_duration:.2f} seconds")
                        
                        # Step 2: Extract audio
                        st.write("🎵 **Extracting audio from video...**")
                        audio_path = extract_audio(video_path)
                        if not audio_path:
                            st.error("Failed to extract audio")
                            return
                        st.success("✅ Audio extracted")
                        
                        # Step 3: Transcribe
                        st.write("📝 **Transcribing audio...**")
                        source_language, segments = transcribe_audio(audio_path)
                        if not segments:
                            st.error("Failed to transcribe audio")
                            return
                        st.success(f"✅ Transcribed {len(segments)} segments")
                        
                        # Show transcription preview
                        with st.expander("View Transcription Preview"):
                            for i, segment in enumerate(segments[:3]):
                                st.write(f"[{segment.start:.1f}s - {segment.end:.1f}s]: {segment.text}")
                        
                        # Step 4: Generate subtitles
                        st.write("📄 **Generating subtitles...**")
                        original_subtitle_path = generate_subtitle_file(segments, temp_dir)
                        st.success("✅ Subtitles generated")
                        
                        # Step 5: Translate
                        st.write("🌍 **Translating subtitles...**")
                        translated_subtitle_path = translate_subtitles(
                            original_subtitle_path, 
                            target_language,
                            source_language
                        )
                        if not translated_subtitle_path:
                            st.error("Failed to translate subtitles")
                            return
                        st.success("✅ Translation completed")
                        
                        # Step 6: Generate translated audio
                        st.write("🔊 **Generating translated audio...**")
                        translated_audio_path = create_translated_audio_ffmpeg(
                            translated_subtitle_path,
                            target_language,
                            temp_dir,
                            video_duration
                        )
                        if not translated_audio_path:
                            st.error("Failed to generate translated audio")
                            return
                        st.success("✅ Translated audio generated")
                        
                        # Step 7: Create final video
                        st.write("🎬 **Creating final dubbed video...**")
                        final_video_path = replace_audio_ffmpeg(
                            video_path,
                            translated_audio_path,
                            temp_dir
                        )
                        if not final_video_path:
                            st.error("Failed to create final video")
                            return
                        st.success("✅ Final video created")
                    
                    # Success section
                    st.markdown("---")
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.balloons()
                    st.success("🎉 Video dubbing completed successfully!")
                    
                    # Display final video
                    st.subheader("🎬 Dubbed Video Preview")
                    st.video(final_video_path)
                    
                    # Download button
                    st.subheader("📥 Download Your Dubbed Video")
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
                    st.markdown("""
                    <div class='warning-box'>
                    <strong>Troubleshooting tips:</strong>
                    - Try a shorter video (under 1 minute)
                    - Ensure the video has clear audio
                    - Try a different target language
                    - Check your internet connection
                    </div>
                    """, unsafe_allow_html=True)
                
                finally:
                    st.session_state.processing = False
        
        elif not uploaded_file:
            st.info("👆 Please upload a video file to start dubbing")
        
        # Display processing status
        if st.session_state.processing:
            st.warning("🔄 Processing in progress... Please don't close the browser.")

    # Instructions section
    st.markdown("---")
    st.header("📖 How It Works")
    
    steps = [
        ("1. Upload", "Upload your video file (MP4, AVI, MOV)"),
        ("2. Transcribe", "AI automatically transcribes the speech to text"),
        ("3. Translate", "Text is translated to your chosen language"),
        ("4. Generate Audio", "AI voice reads the translated text"),
        ("5. Dub Video", "New audio is synced with your video")
    ]
    
    for step, description in steps:
        with st.expander(step):
            st.write(description)

# Run the app
if __name__ == "__main__":
    main()
