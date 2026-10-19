# Required in raw and formatted modes. Build-time provisioning only: runtime
# uses transcribe's native CPU Silero implementation, never a Python backend.
# Include after add_executable(mika).
find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter)
set(speech_stage "${CMAKE_BINARY_DIR}/_deps/speech")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/fetch_speech_assets.py"
    --stage "${speech_stage}"
    COMMAND_ERROR_IS_FATAL ANY)
add_custom_target(mika-speech-assets ALL
    COMMAND "${CMAKE_COMMAND}" -E rm -rf "$<TARGET_FILE_DIR:mika>/speech"
    COMMAND "${CMAKE_COMMAND}" -E copy_directory "${speech_stage}/payload"
        "$<TARGET_FILE_DIR:mika>/speech"
    VERBATIM)
add_dependencies(mika mika-speech-assets)
install(DIRECTORY "${speech_stage}/payload/" DESTINATION bin/speech)
