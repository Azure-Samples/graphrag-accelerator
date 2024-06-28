import streamlit as st

if "edit_button" not in st.session_state:
    st.session_state.edit_button = False
if "save_button" not in st.session_state:
    st.session_state.save_button = False


def edit_button():
    st.session_state.edit_button = not st.session_state.edit_button


def save_button():
    st.success("Prompts saved!")
    st.session_state.save_button = not st.session_state.save_button
    st.session_state.edit_button = False


col1, col2 = st.columns([1, 1])
with col1:
    st.button("Edit Prompts", on_click=edit_button)
    # with col2:
    st.button("Save Prompts", on_click=save_button)

st.text_area(
    "This is a prompt that can be edited", disabled=not st.session_state.edit_button
)
if st.session_state.save_button:
    # The message and nested widget will remain on the page
    download = st.download_button(
        "Download Prompts",
        "This is a prompts.",
        "example.txt",
        mime="application/x-zip",
    )

import streamlit as st

if "stage" not in st.session_state:
    st.session_state.stage = 0


def set_state(i):
    st.session_state.stage = i


if st.session_state.stage == 0:
    st.button("Begin", on_click=set_state, args=[1])

if st.session_state.stage >= 1:
    name = st.text_input("Name", on_change=set_state, args=[2])

if st.session_state.stage >= 2:
    st.write(f"Hello {name}!")
    color = st.selectbox(
        "Pick a Color",
        [None, "red", "orange", "green", "blue", "violet"],
        on_change=set_state,
        args=[3],
    )
    if color is None:
        set_state(2)

if st.session_state.stage >= 3:
    st.write(f":{color}[Thank you!]")
    st.button("Start Over", on_click=set_state, args=[0])
