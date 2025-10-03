import streamlit as st
import os
import tempfile
import math
import time
import base64
from pathlib import Path

# Import with proper error handling
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    st.warning("Faster-Whisper not available, using fallback")

try:
    import whisper
    OPENAI_WHISPER_AVAILABLE = True
except ImportError:
    OPENAI_WHISPER_AVAILABLE = False
    st.warning("OpenAI Whisper not available")

try:
    from moviepy.editor import VideoFileClip, AudioFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    st.error("MoviePy is required but not available")

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    st.error("PyDub is required but not available")

try:
    import pysrt
    PYSRT_AVAILABLE = True
except ImportError:
    PYSRT_AVAILABLE = False
    st.error("PySrt is required but not available")

try:
    from translate import Translator
    TRANSLATE_AVAILABLE = True
except ImportError:
    TRANSLATE_AVAILABLE = False
    st.error("Translate is required but not available")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    st.error("gTTS is required but not available")

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
    .step-box {
        padding: 15px;
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<div class="main-header">🎬 AI Video Dubbing App</div>', unsafe_allow_html=True)
st.markdown("**Upload a video and get it dubbed in any language automatically!**")

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False

# Helper functions
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

def extract_audio(video_path):
    """Extract audio from video using MoviePy"""
    try:
        video = VideoFileClip(video_path)
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_audio.close()
        
        # Extract audio
        audio = video.audio
        audio.write_audiofile(temp_audio.name, verbose=False, logger=None)
        
        # Close clips to free memory
        audio.close()
        video.close()
        
        return temp_audio.name
    except Exception as e:
        st.error(f"Error extracting audio: {str(e)}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using available Whisper model"""
    try:
        if FASTER_WHISPER_AVAILABLE:
            # Use faster-whisper
            model = WhisperModel("base")
            segments, info = model.transcribe(audio_path, beam_size=5)
            language = info[0]
            segments = list(segments)
        elif OPENAI_WHISPER_AVAILABLE:
            # Use OpenAI Whisper as fallback
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            language = result['language']
            
            # Convert to compatible format
            class Segment:
                def __init__(self, start, end, text):
                    self.start = start
                    self.end = end
                    self.text = text
            
            segments = [Segment(s['start'], s['end'], s['text']) for s in result['segments']]
        else:
            st.error("No transcription engine available")
            return None, None
        
        st.info(f"Detected language: {language}")
        return language, segments
        
    except Exception as e:
        st.error(f"Error in transcription: {str(e)}")
        return None, None

def generate_subtitle_file(segments, output_dir):
    """Generate subtitle file from segments"""
    try:
        subtitle_file = os.path.join(output_dir, "original_subtitles.srt")
        text = ""
        for index, segment in enumerate(segments):
            segment_start = format_time(segment.start)
            segment_end = format_time(segment.end)
            text += f"{str(index+1)}\n"
            text += f"{segment_start} --> {segment_end}\n"
            text += f"{segment.text}\n\n"

        with open(subtitle_file, "w", encoding='utf-8') as f:
            f.write(text)

        return subtitle_file
    except Exception as e:
        st.error(f"Error generating subtitles: {str(e)}")
        return None

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
                if i % 5 == 0:  # Update every 5 segments
                    progress = (i + 1) / len(subs)
                    progress_bar.progress(progress)
                    status_text.text(f"Translating... {i+1}/{len(subs)}")
                
            except Exception as e:
                st.warning(f"Could not translate line {i+1}: {str(e)}")
                # Keep original text if translation fails
                translated_subs.append(sub)
        
        translated_subtitle_path = subtitle_path.replace('.srt', f'_translated_{target_language}.srt')
        translated_subs.save(translated_subtitle_path, encoding='utf-8')
        status_text.text("✅ Translation completed!")
        return translated_subtitle_path
    
    except Exception as e:
        st.error(f"Error in translation: {str(e)}")
        return None

def generate_translated_audio(translated_subtitle_path, target_language, video_duration, output_dir):
    """Generate translated audio with proper timing"""
    try:
        subs = pysrt.open(translated_subtitle_path)
        
        # Create a silent audio segment for the entire video duration
        combined_audio = AudioSegment.silent(duration=int(video_duration * 1000))  # Convert to milliseconds
        
        for i, sub in enumerate(subs):
            try:
                start_time = sub.start.ordinal / 1000.0  # Convert to seconds
                end_time = sub.end.ordinal / 1000.0
                text = sub.text.strip()
                
                if text:
                    # Generate TTS audio
                    tts = gTTS(text=text, lang=target_language, slow=False)
                    temp_mp3 = os.path.join(output_dir, f"temp_{i}.mp3")
                    tts.save(temp_mp3)
                    
                    # Load the generated audio
                    segment_audio = AudioSegment.from_mp3(temp_mp3)
                    
                    # Calculate positions in milliseconds
                    start_ms = int(start_time * 1000)
                    
                    # Ensure the segment fits within the video duration
                    if start_ms + len(segment_audio) <= len(combined_audio):
                        # Overlay the TTS audio at the correct position
                        combined_audio = combined_audio.overlay(segment_audio, position=start_ms)
                    
                    # Clean up temp file
                    os.remove(temp_mp3)
                    
            except Exception as e:
                st.warning(f"Could not process segment {i+1}: {str(e)}")
                continue
        
        # Export the final audio
        output_audio_path = os.path.join(output_dir, "translated_audio.wav")
        combined_audio.export(output_audio_path, format="wav")
        return output_audio_path
        
    except Exception as e:
        st.error(f"Error generating translated audio: {str(e)}")
        return None

def create_dubbed_video(original_video_path, translated_audio_path, output_dir):
    """Create final dubbed video"""
    try:
        # Load original video
        video = VideoFileClip(original_video_path)
        
        # Load translated audio
        new_audio = AudioFileClip(translated_audio_path)
        
        # Set the new audio to the video
        final_video = video.set_audio(new_audio)
        
        # Export the final video
        output_video_path = os.path.join(output_dir, "dubbed_video.mp4")
        final_video.write_videofile(
            output_video_path,
            codec='libx264',
            audio_codec='aac',
            verbose=False,
            logger=None,
            temp_audiofile='temp-audio.m4a',
            remove_temp=True
        )
        
        # Close clips to free memory
        video.close()
        new_audio.close()
        final_video.close()
        
        return output_video_path
        
    except Exception as e:
        st.error(f"Error creating dubbed video: {str(e)}")
        return None

def get_video_duration(video_path):
    """Get video duration using MoviePy"""
    try:
        video = VideoFileClip(video_path)
        duration = video.duration
        video.close()
        return duration
    except Exception as e:
        st.error(f"Error getting video duration: {str(e)}")
        return None

# Main app
def main():
    # Check dependencies
    if not all([MOVIEPY_AVAILABLE, PYDUB_AVAILABLE, PYSRT_AVAILABLE, TRANSLATE_AVAILABLE, GTTS_AVAILABLE]):
        st.error("🚨 Critical dependencies missing. Please check the requirements.")
        return
    
    if not any([FASTER_WHISPER_AVAILABLE, OPENAI_WHISPER_AVAILABLE]):
        st.error("🚨 No transcription engine available.")
        return

    # Sidebar
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
        <strong>💡 Tips for best results:</strong>
        - Use short videos (1-3 minutes)
        - Ensure clear audio in original
        - Processing takes 2-5 minutes
        - First run downloads AI models
        </div>
        """, unsafe_allow_html=True)

    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Video")
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'mov', 'avi', 'mkv'],
            help="Supported formats: MP4, MOV, AVI, MKV"
        )
        
        if uploaded_file is not None:
            file_size = uploaded_file.size / (1024 * 1024)  # MB
            st.write(f"**File:** {uploaded_file.name}")
            st.write(f"**Size:** {file_size:.2f} MB")
            
            # Display video
            st.video(uploaded_file)
    
    with col2:
        st.header("🎯 Processing")
        
        if uploaded_file is not None and st.button("🚀 Start Video Dubbing", type="primary", use_container_width=True):
            if file_size > 100:
                st.error("Please upload a video under 100MB")
                return
                
            st.session_state.processing = True
            
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Save uploaded file
                    video_path = os.path.join(temp_dir, "input_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Processing container
                    processing_container = st.container()
                    
                    with processing_container:
                        st.subheader("🔄 Processing Steps")
                        
                        # Step 1: Get video duration
                        with st.status("📏 Getting video duration...", expanded=True) as status:
                            duration = get_video_duration(video_path)
                            if duration:
                                st.write(f"Video duration: {duration:.2f} seconds")
                                status.update(label="✅ Video duration obtained", state="complete")
                            else:
                                st.error("Failed to get video duration")
                                return
                        
                        # Step 2: Extract audio
                        with st.status("🎵 Extracting audio from video...", expanded=True) as status:
                            audio_path = extract_audio(video_path)
                            if audio_path:
                                st.write("Audio extracted successfully")
                                status.update(label="✅ Audio extracted", state="complete")
                            else:
                                st.error("Failed to extract audio")
                                return
                        
                        # Step 3: Transcribe
                        with st.status("📝 Transcribing audio...", expanded=True) as status:
                            source_language, segments = transcribe_audio(audio_path)
                            if segments:
                                st.write(f"Transcribed {len(segments)} segments")
                                status.update(label="✅ Transcription completed", state="complete")
                            else:
                                st.error("Failed to transcribe audio")
                                return
                        
                        # Step 4: Generate subtitles
                        with st.status("📄 Generating subtitles...", expanded=True) as status:
                            subtitle_path = generate_subtitle_file(segments, temp_dir)
                            if subtitle_path:
                                st.write("Subtitles generated")
                                status.update(label="✅ Subtitles generated", state="complete")
                            else:
                                st.error("Failed to generate subtitles")
                                return
                        
                        # Step 5: Translate
                        with st.status("🌍 Translating to target language...", expanded=True) as status:
                            translated_subtitle_path = translate_subtitles(
                                subtitle_path, target_language, source_language
                            )
                            if translated_subtitle_path:
                                st.write("Translation completed")
                                status.update(label="✅ Translation completed", state="complete")
                            else:
                                st.error("Failed to translate subtitles")
                                return
                        
                        # Step 6: Generate translated audio
                        with st.status("🔊 Generating translated audio...", expanded=True) as status:
                            translated_audio_path = generate_translated_audio(
                                translated_subtitle_path, target_language, duration, temp_dir
                            )
                            if translated_audio_path:
                                st.write("Translated audio generated")
                                status.update(label="✅ Translated audio generated", state="complete")
                            else:
                                st.error("Failed to generate translated audio")
                                return
                        
                        # Step 7: Create final video
                        with st.status("🎬 Creating dubbed video...", expanded=True) as status:
                            final_video_path = create_dubbed_video(
                                video_path, translated_audio_path, temp_dir
                            )
                            if final_video_path:
                                st.write("Dubbed video created successfully")
                                status.update(label="✅ Dubbed video created", state="complete")
                            else:
                                st.error("Failed to create dubbed video")
                                return
                    
                    # Success section
                    st.markdown("---")
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.balloons()
                    st.success("🎉 Video dubbing completed successfully!")
                    
                    # Display final video
                    st.subheader("🎬 Your Dubbed Video")
                    st.video(final_video_path)
                    
                    # Download section
                    st.subheader("📥 Download Results")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Download dubbed video
                        with open(final_video_path, "rb") as f:
                            video_data = f.read()
                        st.download_button(
                            label="🎬 Download Dubbed Video",
                            data=video_data,
                            file_name=f"dubbed_{target_language}_{uploaded_file.name}",
                            mime="video/mp4",
                            type="primary",
                            use_container_width=True
                        )
                    
                    with col2:
                        # Download translated subtitles
                        with open(translated_subtitle_path, "r", encoding='utf-8') as f:
                            subtitle_data = f.read()
                        st.download_button(
                            label="📄 Download Subtitles",
                            data=subtitle_data,
                            file_name=f"subtitles_{target_language}.srt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    
                    with col3:
                        # Download translated audio
                        with open(translated_audio_path, "rb") as f:
                            audio_data = f.read()
                        st.download_button(
                            label="🔊 Download Audio",
                            data=audio_data,
                            file_name=f"audio_{target_language}.wav",
                            mime="audio/wav",
                            use_container_width=True
                        )
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"❌ Processing failed: {str(e)}")
                    st.info("""
                    **Troubleshooting tips:**
                    - Try a shorter video (under 2 minutes)
                    - Ensure the video has clear audio
                    - Try a different target language
                    - Check your internet connection
                    """)
                
                finally:
                    st.session_state.processing = False
        
        elif not uploaded_file:
            st.info("👆 Upload a video file to start dubbing")
        
        if st.session_state.processing:
            st.warning("⏳ Processing... This may take several minutes. Please don't close the browser.")

    # Instructions
    st.markdown("---")
    st.header("📖 How It Works")
    
    steps = [
        ("🎬 Upload Video", "Upload your video file (MP4, MOV, AVI)"),
        ("🎵 Extract Audio", "AI extracts audio from your video"),
        ("📝 Transcribe", "Speech is converted to text using AI"),
        ("🌍 Translate", "Text is translated to your chosen language"),
        ("🔊 Generate Audio", "AI voice reads the translated text"),
        ("🎬 Create Video", "New audio is synced with your video")
    ]
    
    for step, description in steps:
        with st.expander(step, expanded=True):
            st.write(description)

if __name__ == "__main__":
    main()
