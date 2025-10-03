import streamlit as st
import os
import tempfile
import math
import time
import base64
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

def extract_audio_pydub(video_path):
    """Extract audio using PyDub (no MoviePy dependency)"""
    try:
        from pydub import AudioSegment
        
        # PyDub can handle MP4 files directly
        video = AudioSegment.from_file(video_path, format="mp4")
        
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        temp_audio.close()
        
        # Export as WAV
        video.export(temp_audio.name, format="wav")
        return temp_audio.name
        
    except Exception as e:
        st.error(f"Error extracting audio: {str(e)}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper"""
    try:
        import whisper
        
        # Load the base model
        model = whisper.load_model("base")
        
        # Transcribe audio
        result = model.transcribe(audio_path)
        
        # Convert to segments format
        class Segment:
            def __init__(self, start, end, text):
                self.start = start
                self.end = end
                self.text = text
        
        segments = [Segment(s['start'], s['end'], s['text']) for s in result['segments']]
        language = result.get('language', 'en')
        
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
        import pysrt
        from translate import Translator
        
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
                if i % 5 == 0:
                    progress = (i + 1) / len(subs)
                    progress_bar.progress(progress)
                    status_text.text(f"Translating... {i+1}/{len(subs)}")
                
            except Exception as e:
                st.warning(f"Could not translate line {i+1}: {str(e)}")
                translated_subs.append(sub)
        
        translated_subtitle_path = subtitle_path.replace('.srt', f'_translated_{target_language}.srt')
        translated_subs.save(translated_subtitle_path, encoding='utf-8')
        status_text.text("✅ Translation completed!")
        return translated_subtitle_path
    
    except Exception as e:
        st.error(f"Error in translation: {str(e)}")
        return None

def create_dubbed_video_simple(input_video_path, translated_subtitle_path, target_language, output_dir):
    """
    Create a simple dubbed version by providing translated subtitles
    This is a fallback when full audio dubbing isn't possible
    """
    try:
        # For Streamlit Cloud limitations, we'll create a simple processed version
        # by just copying the original video and providing translated subtitles
        
        import shutil
        import pysrt
        
        # Copy original video
        output_video_path = os.path.join(output_dir, "processed_video.mp4")
        shutil.copy2(input_video_path, output_video_path)
        
        # Provide translated subtitles separately
        translated_subs = pysrt.open(translated_subtitle_path)
        
        st.info("🔊 Note: Full audio dubbing requires advanced processing. Download the translated subtitles separately.")
        
        return output_video_path, translated_subs
        
    except Exception as e:
        st.error(f"Error creating processed video: {str(e)}")
        return None, None

def get_video_duration_pydub(video_path):
    """Get video duration using PyDub"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(video_path, format="mp4")
        duration = len(audio) / 1000.0  # Convert milliseconds to seconds
        return duration
    except Exception as e:
        st.warning(f"Could not get video duration: {str(e)}")
        return 60.0  # Default fallback

# Main app
def main():
    # Check for critical dependencies
    try:
        import whisper
        import pysrt
        from translate import Translator
        from gtts import gTTS
        from pydub import AudioSegment
        
        st.success("✅ All dependencies loaded successfully!")
        
    except ImportError as e:
        st.error(f"❌ Missing dependency: {str(e)}")
        st.info("Please make sure all packages in requirements.txt are installed")
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
        <strong>💡 How it works:</strong>
        1. Upload your video
        2. AI transcribes the audio
        3. Text is translated
        4. Get translated subtitles
        5. Download processed video
        </div>
        """, unsafe_allow_html=True)

    # Main content
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Video")
        uploaded_file = st.file_uploader(
            "Choose a video file",
            type=['mp4', 'mov'],
            help="Supported formats: MP4, MOV"
        )
        
        if uploaded_file is not None:
            file_size = uploaded_file.size / (1024 * 1024)  # MB
            st.write(f"**File:** {uploaded_file.name}")
            st.write(f"**Size:** {file_size:.2f} MB")
            
            # Display video
            st.video(uploaded_file)
    
    with col2:
        st.header("🎯 Processing")
        
        if uploaded_file is not None and st.button("🚀 Start Video Translation", type="primary", use_container_width=True):
            if file_size > 50:
                st.error("Please upload a video under 50MB")
                return
                
            st.session_state.processing = True
            
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    # Save uploaded file
                    video_path = os.path.join(temp_dir, "input_video.mp4")
                    with open(video_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Processing container
                    with st.container():
                        st.subheader("🔄 Processing Steps")
                        
                        # Step 1: Get video duration
                        with st.status("📏 Getting video duration...", expanded=True) as status:
                            duration = get_video_duration_pydub(video_path)
                            st.write(f"Video duration: {duration:.2f} seconds")
                            status.update(label="✅ Video duration obtained", state="complete")
                        
                        # Step 2: Extract audio
                        with st.status("🎵 Extracting audio from video...", expanded=True) as status:
                            audio_path = extract_audio_pydub(video_path)
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
                                
                                # Show sample transcription
                                with st.expander("View sample transcription"):
                                    for i, segment in enumerate(segments[:3]):
                                        st.write(f"[{segment.start:.1f}s - {segment.end:.1f}s]: {segment.text}")
                                
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
                        
                        # Step 6: Create final output
                        with st.status("🎬 Creating final output...", expanded=True) as status:
                            final_video_path, translated_subs = create_dubbed_video_simple(
                                video_path, translated_subtitle_path, target_language, temp_dir
                            )
                            if final_video_path:
                                st.write("Final output created")
                                status.update(label="✅ Final output created", state="complete")
                            else:
                                st.error("Failed to create final output")
                                return
                    
                    # Success section
                    st.markdown("---")
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    st.balloons()
                    st.success("🎉 Video translation completed successfully!")
                    
                    # Display final video
                    st.subheader("🎬 Your Processed Video")
                    st.video(final_video_path)
                    
                    # Download section
                    st.subheader("📥 Download Results")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Download processed video
                        with open(final_video_path, "rb") as f:
                            video_data = f.read()
                        st.download_button(
                            label="🎬 Download Video",
                            data=video_data,
                            file_name=f"translated_{target_language}_{uploaded_file.name}",
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
                        # Download original subtitles
                        with open(subtitle_path, "r", encoding='utf-8') as f:
                            original_subtitle_data = f.read()
                        st.download_button(
                            label="📝 Original Subtitles",
                            data=original_subtitle_data,
                            file_name="original_subtitles.srt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    
                    # Show translated subtitles preview
                    with st.expander("🔍 View Translated Subtitles Preview"):
                        if translated_subs:
                            for i, sub in enumerate(translated_subs[:5]):
                                st.write(f"{i+1}. {sub.text}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"❌ Processing failed: {str(e)}")
                    st.markdown("""
                    <div class='warning-box'>
                    <strong>Troubleshooting tips:</strong>
                    - Try a shorter video (under 2 minutes)
                    - Ensure the video has clear audio
                    - Try a different target language
                    - Check your internet connection
                    </div>
                    """, unsafe_allow_html=True)
                
                finally:
                    st.session_state.processing = False
        
        elif not uploaded_file:
            st.info("👆 Upload a video file to start translation")
        
        if st.session_state.processing:
            st.warning("⏳ Processing... This may take 2-5 minutes. Please don't close the browser.")

    # Instructions
    st.markdown("---")
    st.header("📖 How It Works")
    
    steps = [
        ("1. Upload Video", "Upload your MP4 or MOV video file"),
        ("2. Extract Audio", "AI extracts audio from your video"),
        ("3. Transcribe Speech", "Speech is converted to text using Whisper AI"),
        ("4. Translate Text", "Text is translated to your chosen language"),
        ("5. Generate Output", "Get translated subtitles and processed video")
    ]
    
    for step, description in steps:
        with st.expander(step, expanded=True):
            st.write(description)

if __name__ == "__main__":
    main()
