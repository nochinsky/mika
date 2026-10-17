cmake_minimum_required(VERSION 3.24)
project(mika VERSION 0.1.1 LANGUAGES C CXX)

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

include(FetchContent)
include(CTest)
find_package(Threads REQUIRED)
find_package(CURL 7.85 REQUIRED)
find_package(OpenSSL 1.1.1 REQUIRED COMPONENTS Crypto)

# Release bundles use CPU feature-dispatched modules: fast on modern CPUs,
# with a baseline module for older x86-64 CPUs. Ordinary source builds stay static.
option(MIKA_RELEASE_BUNDLE "Build relocatable, CPU-dispatched release libraries" OFF)
if(MIKA_RELEASE_BUNDLE)
    set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
    if(UNIX AND NOT APPLE)
        set(CMAKE_INSTALL_RPATH "$ORIGIN/../lib;$ORIGIN")
    endif()
endif()

# Fixed sources and archive hashes: never build an unpinned upstream branch.
set(TRANSCRIBE_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_BUILD_SHARED ${MIKA_RELEASE_BUNDLE} CACHE BOOL "" FORCE)
set(TRANSCRIBE_GGML_BACKEND_DL ${MIKA_RELEASE_BUNDLE} CACHE BOOL "" FORCE)
set(TRANSCRIBE_INSTALL ${MIKA_RELEASE_BUNDLE} CACHE BOOL "" FORCE)
set(TRANSCRIBE_METAL OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_VULKAN OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_CUDA OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_HIP OFF CACHE BOOL "" FORCE)
set(TRANSCRIBE_USE_SYSTEM_BLAS OFF CACHE BOOL "" FORCE)
# Baseline CPU build by default; local native tuning is an explicit opt-in.
option(MIKA_NATIVE_CPU "Optimize for this build machine; binary may not be portable" OFF)
if(MIKA_RELEASE_BUNDLE)
    set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
else()
    set(GGML_NATIVE ${MIKA_NATIVE_CPU} CACHE BOOL "" FORCE)
endif()
set(TRANSCRIBE_X86_CONSERVATIVE ON CACHE BOOL "" FORCE)
set(GGML_CPU_ALL_VARIANTS ${MIKA_RELEASE_BUNDLE} CACHE BOOL "" FORCE)
FetchContent_Declare(transcribe
    URL https://codeload.github.com/handy-computer/transcribe.cpp/tar.gz/b61b7f936e4e728f8999a8c3e98c7112e700410e
    URL_HASH SHA256=9e8f32228cf633b20f21cb321371f887fb96537d6a76f062d516f488818402db
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_Declare(miniaudio
    URL https://codeload.github.com/mackron/miniaudio/tar.gz/9634bedb5b5a2ca38c1ee7108a9358a4e233f14d
    URL_HASH SHA256=1a3a79b80fc6f0b0cc155e28b954a598e0ddfa2db64e2afa8466be88c476fa55
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
    SOURCE_SUBDIR mika-no-subproject)
FetchContent_MakeAvailable(transcribe miniaudio)
# The pinned backend assumes its own include/ is at CMAKE_SOURCE_DIR.
# Supply the correct path when embedding it as a subproject.
target_include_directories(transcribe PUBLIC "${transcribe_SOURCE_DIR}/include")

add_library(mika_miniaudio STATIC "${miniaudio_SOURCE_DIR}/miniaudio.c")
target_include_directories(mika_miniaudio SYSTEM PUBLIC "${miniaudio_SOURCE_DIR}")
target_compile_definitions(mika_miniaudio PUBLIC
    MA_NO_ENGINE MA_NO_NODE_GRAPH MA_NO_RESOURCE_MANAGER MA_NO_GENERATION
    MA_NO_ENCODING MA_NO_FLAC MA_NO_MP3 MA_NO_NULL)
target_link_libraries(mika_miniaudio PUBLIC Threads::Threads ${CMAKE_DL_LIBS})
if(UNIX)
    target_link_libraries(mika_miniaudio PUBLIC m)
endif()

option(MIKA_SANITIZERS "Instrument Mika-owned code with AddressSanitizer and UBSan" OFF)
function(mika_warnings target)
    if(MIKA_SANITIZERS AND NOT MSVC)
        target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
        target_link_options(${target} PUBLIC -fsanitize=address,undefined)
    endif()
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /utf-8)
        target_compile_definitions(${target} PRIVATE _CRT_SECURE_NO_WARNINGS)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
        target_compile_definitions(${target} PRIVATE _POSIX_C_SOURCE=200809L)
    endif()
endfunction()

add_library(mika_platform STATIC src/platform.c)
target_include_directories(mika_platform PUBLIC src)
if(WIN32)
    target_link_libraries(mika_platform PUBLIC shell32 ole32 uuid)
endif()
mika_warnings(mika_platform)

add_library(mika_model STATIC src/model.c)
target_link_libraries(mika_model PUBLIC mika_platform CURL::libcurl OpenSSL::Crypto)
mika_warnings(mika_model)

add_library(mika_pcm STATIC src/pcm.c)
target_include_directories(mika_pcm PUBLIC src)
mika_warnings(mika_pcm)

add_library(mika_audio STATIC src/audio.c)
target_link_libraries(mika_audio PUBLIC mika_pcm mika_miniaudio mika_platform)
mika_warnings(mika_audio)

add_library(mika_engine STATIC src/engine.c)
target_include_directories(mika_engine PUBLIC src)
target_link_libraries(mika_engine PUBLIC transcribe mika_platform)
mika_warnings(mika_engine)

add_executable(mika src/main.c)
target_compile_definitions(mika PRIVATE MIKA_VERSION="${PROJECT_VERSION}")
target_link_libraries(mika PRIVATE mika_engine mika_model mika_audio)
mika_warnings(mika)

install(TARGETS mika RUNTIME DESTINATION bin)
install(FILES README.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md LICENSE DESTINATION share/doc/mika)
install(DIRECTORY docs/ DESTINATION share/doc/mika/docs)
install(DIRECTORY licenses/ DESTINATION share/licenses/mika)

if(BUILD_TESTING)
    add_executable(mika-inference-test tests/inference.c)
    target_link_libraries(mika-inference-test PRIVATE mika_engine mika_miniaudio mika_platform)
    mika_warnings(mika-inference-test)
    # CI can validate installed/relocated libraries; this probe is never packaged.
    install(TARGETS mika-inference-test RUNTIME DESTINATION bin
        COMPONENT Validation EXCLUDE_FROM_ALL)

    add_executable(mika-unit tests/unit.c)
    target_link_libraries(mika-unit PRIVATE mika_model mika_pcm)
    mika_warnings(mika-unit)
    add_test(NAME unit COMMAND mika-unit "${CMAKE_CURRENT_BINARY_DIR}/test-data/unit")
    set_tests_properties(unit PROPERTIES TIMEOUT 30)

    add_executable(mika-cli-fixture src/main.c tests/cli_stubs.c)
    target_link_libraries(mika-cli-fixture PRIVATE mika_platform mika_pcm)
    target_compile_definitions(mika-cli-fixture PRIVATE MIKA_VERSION="${PROJECT_VERSION}")
    mika_warnings(mika-cli-fixture)

    add_executable(mika-install-fixture tests/install_fixture.c)
    mika_warnings(mika-install-fixture)

    add_executable(mika-download-test tests/download.c)
    target_link_libraries(mika-download-test PRIVATE mika_model)
    mika_warnings(mika-download-test)

    add_executable(mika-audio-devices tests/audio_devices.c)
    target_link_libraries(mika-audio-devices PRIVATE mika_miniaudio)
    mika_warnings(mika-audio-devices)

    find_package(Python3 3.8 COMPONENTS Interpreter)
    if(Python3_Interpreter_FOUND)
        add_test(NAME cli COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/cli.py"
            "$<TARGET_FILE:mika>" "$<TARGET_FILE:mika-cli-fixture>")
        add_test(NAME download COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/download.py"
            "$<TARGET_FILE:mika-download-test>")
        set_tests_properties(cli download PROPERTIES TIMEOUT 90)
        if(WIN32)
            add_test(NAME windows-console COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/windows_console.py"
                "$<TARGET_FILE:mika-cli-fixture>")
            set_tests_properties(windows-console PROPERTIES TIMEOUT 60)
        endif()
        if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
            add_test(NAME installers COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/installers.py"
                "${CMAKE_CURRENT_SOURCE_DIR}/install.sh")
            set_tests_properties(installers PROPERTIES TIMEOUT 60)
        endif()
    endif()

    # Opt-in integration test: the default suite never downloads models or records audio.
    set(MIKA_TEST_MODEL "" CACHE FILEPATH "Verified Granite GGUF for the real-model test")
    if(MIKA_TEST_MODEL)
        add_test(NAME real-model COMMAND mika-inference-test "${MIKA_TEST_MODEL}"
            "${transcribe_SOURCE_DIR}/samples/jfk.wav")
        set_tests_properties(real-model PROPERTIES TIMEOUT 120
            PASS_REGULAR_EXPRESSION "ask not what your country can do for you")
    endif()
endif()
