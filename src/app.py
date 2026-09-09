import streamlit as st
from config import Config
from agent import generate_cinematic_package

# Validate config on startup
Config.validate()

st.set_page_config(page_title="AI Cinematographer", layout="wide")
st.title("🎬 AI Cinematographer: Pre-Production Engine")

scene_input = st.text_area("Scene Description:", placeholder="A weary detective sitting alone at a diner at 3 AM...")

if st.button("Generate Shot & Storyboard", type="primary"):
    if not scene_input.strip():
        st.warning("Please enter a scene description first.")
    else:
        with st.spinner("Analyzing scene and generating storyboard..."):
            try:
                # One clean function call to the agent
                shot_data, generated_image = generate_cinematic_package(scene_input)
                
                st.divider()
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    st.image(generated_image, caption=shot_data.image_generation_prompt, use_container_width=True)
                    
                with col2:
                    st.subheader("Technical Specifications")
                    st.markdown(f"**Shot Type:** `{shot_data.shot_type}`")
                    st.markdown(f"**Angle:** `{shot_data.camera_angle}`")
                    st.markdown(f"**Focal Length:** `{shot_data.focal_length}`")
                    st.markdown(f"**Lighting & Exposure:** {shot_data.lighting_and_exposure}")
                    st.markdown(f"**Subject Action:** {shot_data.subject_action}")
                    st.markdown(f"**Environment:** {shot_data.environmental_context}")
                    
            except Exception as e:
                st.error(str(e))