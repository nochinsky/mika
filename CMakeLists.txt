cmake_minimum_required(VERSION 3.24)
project(mika VERSION 0.1.2 LANGUAGES C CXX)

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

add_library(mika_punctuation_guard STATIC src/punctuation.c)
target_include_directories(mika_punctuation_guard PUBLIC src)
mika_warnings(mika_punctuation_guard)
set_target_properties(mika_punctuation_guard PROPERTIES POSITION_INDEPENDENT_CODE ON)
add_library(mika_fullstop_render STATIC src/fullstop_render.cpp)
target_link_libraries(mika_fullstop_render PUBLIC mika_punctuation_guard)
set_target_properties(mika_fullstop_render PROPERTIES POSITION_INDEPENDENT_CODE ON)
mika_warnings(mika_fullstop_render)

add_executable(mika src/main.c)
target_compile_definitions(mika PRIVATE MIKA_VERSION="${PROJECT_VERSION}")
target_link_libraries(mika PRIVATE mika_engine mika_model mika_audio)
mika_warnings(mika)

# Unreleased, double opt-in prototype. Default builds neither fetch these assets
# nor depend on ONNX Runtime. Keep experimental builds out of release packages.
option(MIKA_EXPERIMENTAL_PUNCTUATION "Build the unreleased --punctuate prototype" OFF)
if(MIKA_EXPERIMENTAL_PUNCTUATION)
    if(MIKA_RELEASE_BUNDLE)
        message(FATAL_ERROR "Punctuation is an unreleased prototype; disable MIKA_RELEASE_BUNDLE")
    endif()
    if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$" OR
       NOT (WIN32 OR CMAKE_SYSTEM_NAME STREQUAL "Linux"))
        message(FATAL_ERROR "Punctuation prototype requires native Linux/Windows x86-64")
    endif()
    find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter)
    if(WIN32)
        set(punctuation_platform windows)
    else()
        set(punctuation_platform linux)
    endif()
    set(punctuation_stage "${CMAKE_BINARY_DIR}/_deps/punctuation")
    execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/fetch_punctuation.py"
        --stage "${punctuation_stage}" --platform "${punctuation_platform}"
        COMMAND_ERROR_IS_FATAL ANY)
    # Older, self-contained SentencePiece avoids the newer upstream's automatic
    # unpinned Abseil checkout. Build only its inference static library.
    set(SPM_ENABLE_SHARED OFF CACHE BOOL "" FORCE)
    set(SPM_ENABLE_TCMALLOC OFF CACHE BOOL "" FORCE)
    set(SPM_BUILD_TEST OFF CACHE BOOL "" FORCE)
    set(SPM_ABSL_PROVIDER internal CACHE STRING "" FORCE)
    set(SPM_PROTOBUF_PROVIDER internal CACHE STRING "" FORCE)
    FetchContent_Declare(sentencepiece
        URL https://codeload.github.com/google/sentencepiece/tar.gz/31646a467d2051eb904e0b45de3a73e91fe1c1e3
        URL_HASH SHA256=b4eb17e6bea5c9380ddd79d04d01d6aa5e280be8f3e3cef1f745a80e6d9451ce
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
        SOURCE_SUBDIR mika-no-subproject)
    FetchContent_MakeAvailable(sentencepiece)
    add_subdirectory("${sentencepiece_SOURCE_DIR}" "${sentencepiece_BINARY_DIR}" EXCLUDE_FROM_ALL)
    add_library(mika_ort SHARED IMPORTED)
    if(WIN32)
        set_target_properties(mika_ort PROPERTIES
            IMPORTED_LOCATION "${punctuation_stage}/payload/onnxruntime.dll"
            IMPORTED_IMPLIB "${punctuation_stage}/include/onnxruntime.lib")
    else()
        set_target_properties(mika_ort PROPERTIES IMPORTED_LOCATION "${punctuation_stage}/payload/libonnxruntime.so")
    endif()
    add_library(mika-fullstop SHARED src/fullstop.cpp)
    target_compile_definitions(mika-fullstop PRIVATE MIKA_FULLSTOP_BUILD=1)
    target_include_directories(mika-fullstop SYSTEM PRIVATE
        "${punctuation_stage}/include" "${sentencepiece_SOURCE_DIR}/src")
    target_link_libraries(mika-fullstop PRIVATE mika_fullstop_render sentencepiece-static mika_ort)
    set_target_properties(mika-fullstop PROPERTIES CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
    if(UNIX)
        set_target_properties(mika-fullstop PROPERTIES BUILD_WITH_INSTALL_RPATH TRUE INSTALL_RPATH "$ORIGIN")
        target_link_options(mika-fullstop PRIVATE "LINKER:--exclude-libs,ALL")
    endif()
    mika_warnings(mika-fullstop)
    add_library(mika_punctuation STATIC src/punctuation_backend.cpp)
    target_link_libraries(mika_punctuation PUBLIC mika_punctuation_guard mika_model ${CMAKE_DL_LIBS})
    mika_warnings(mika_punctuation)
    if(MSVC)
        # Retain a defensive boundary even for an unexpectedly throwing module.
        # Do not let /EHsc's extern-C-is-nothrow assumption remove the catch.
        target_compile_options(mika_punctuation PRIVATE /EHsc-)
    endif()
    target_compile_definitions(mika PRIVATE MIKA_EXPERIMENTAL_PUNCTUATION=1)
    target_link_libraries(mika PRIVATE mika_punctuation)
    add_custom_target(mika-punctuation-assets ALL
        COMMAND "${CMAKE_COMMAND}" -E rm -rf "$<TARGET_FILE_DIR:mika>/punctuation"
        COMMAND "${CMAKE_COMMAND}" -E copy_directory "${punctuation_stage}/payload"
            "$<TARGET_FILE_DIR:mika>/punctuation"
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different "$<TARGET_FILE:mika-fullstop>"
            "$<TARGET_FILE_DIR:mika>/punctuation/$<TARGET_FILE_NAME:mika-fullstop>")
    add_dependencies(mika-punctuation-assets mika-fullstop)
    add_dependencies(mika mika-punctuation-assets)
    install(DIRECTORY "${punctuation_stage}/payload/" DESTINATION bin/punctuation)
    install(TARGETS mika-fullstop LIBRARY DESTINATION bin/punctuation RUNTIME DESTINATION bin/punctuation)
endif()

install(TARGETS mika RUNTIME DESTINATION bin)
install(FILES README.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md LICENSE DESTINATION share/doc/mika)
install(DIRECTORY docs/ DESTINATION share/doc/mika/docs)
install(DIRECTORY licenses/ DESTINATION share/licenses/mika)

if(BUILD_TESTING)
    add_executable(mika-inference-test tests/inference.c)
    target_link_libraries(mika-inference-test PRIVATE mika_engine mika_miniaudio mika_platform)
    if(WIN32)
        target_link_libraries(mika-inference-test PRIVATE psapi)
    endif()
    mika_warnings(mika-inference-test)
    # CI can validate installed/relocated libraries; this probe is never packaged.
    install(TARGETS mika-inference-test RUNTIME DESTINATION bin
        COMPONENT Validation EXCLUDE_FROM_ALL)

    add_executable(mika-fullstop-unit tests/fullstop_unit.cpp)
    target_link_libraries(mika-fullstop-unit PRIVATE mika_fullstop_render)
    mika_warnings(mika-fullstop-unit)
    add_test(NAME fullstop-unit COMMAND mika-fullstop-unit)
    set_tests_properties(fullstop-unit PROPERTIES TIMEOUT 30)

    add_executable(mika-punctuation-unit tests/punctuation_unit.c)
    target_link_libraries(mika-punctuation-unit PRIVATE mika_punctuation_guard)
    mika_warnings(mika-punctuation-unit)
    add_test(NAME punctuation-unit COMMAND mika-punctuation-unit)
    set_tests_properties(punctuation-unit PROPERTIES TIMEOUT 30)

    if(MIKA_EXPERIMENTAL_PUNCTUATION)
        target_compile_definitions(mika-inference-test PRIVATE MIKA_EXPERIMENTAL_PUNCTUATION=1)
        target_link_libraries(mika-inference-test PRIVATE mika_punctuation)
        add_dependencies(mika-inference-test mika-punctuation-assets)
        add_executable(mika-punctuation-test tests/punctuation_probe.c)
        target_link_libraries(mika-punctuation-test PRIVATE mika_punctuation)
        if(WIN32)
            target_link_libraries(mika-punctuation-test PRIVATE psapi)
        endif()
        mika_warnings(mika-punctuation-test)
        add_dependencies(mika-punctuation-test mika-punctuation-assets)
        add_executable(mika-cli-punctuation-fixture src/main.c tests/cli_stubs.c)
        target_compile_definitions(mika-cli-punctuation-fixture PRIVATE
            MIKA_VERSION="${PROJECT_VERSION}" MIKA_EXPERIMENTAL_PUNCTUATION=1
            mika_model_ensure=mika_fixture_model_ensure)
        target_link_libraries(mika-cli-punctuation-fixture PRIVATE mika_punctuation mika_pcm)
        mika_warnings(mika-cli-punctuation-fixture)
        add_dependencies(mika-cli-punctuation-fixture mika-punctuation-assets)
        add_library(mika-punctuation-fake SHARED tests/punctuation_fake.cpp)
        target_link_libraries(mika-punctuation-fake PRIVATE Threads::Threads)
        target_include_directories(mika-punctuation-fake PRIVATE src)
        target_compile_definitions(mika-punctuation-fake PRIVATE MIKA_FULLSTOP_BUILD=1)
        mika_warnings(mika-punctuation-fake)
        if(MSVC)
            target_compile_options(mika-punctuation-fake PRIVATE /EHsc-)
        endif()
    endif()

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
        add_test(NAME punctuation-evaluation COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/punctuation_evaluation.py")
        set_tests_properties(punctuation-evaluation PROPERTIES TIMEOUT 30)
        add_test(NAME punctuation-fetch COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/punctuation_fetch.py")
        set_tests_properties(punctuation-fetch PROPERTIES TIMEOUT 30)
        if(MIKA_EXPERIMENTAL_PUNCTUATION)
            add_test(NAME punctuation COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/punctuation.py"
                "$<TARGET_FILE:mika-punctuation-test>" "$<TARGET_FILE_DIR:mika>/punctuation"
                "$<TARGET_FILE:mika-punctuation-fake>" "$<TARGET_FILE:mika-cli-punctuation-fixture>")
            set_tests_properties(punctuation PROPERTIES TIMEOUT 120)
        endif()
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
        if(Python3_Interpreter_FOUND)
            if(MIKA_EXPERIMENTAL_PUNCTUATION)
                set(punctuation_long_args --punctuate)
                add_test(NAME real-model-punctuation COMMAND "${Python3_EXECUTABLE}"
                    "${CMAKE_CURRENT_SOURCE_DIR}/tests/punctuation_audio.py"
                    "$<TARGET_FILE:mika-inference-test>" "${MIKA_TEST_MODEL}"
                    "${transcribe_SOURCE_DIR}/samples/jfk.wav")
                set_tests_properties(real-model-punctuation PROPERTIES TIMEOUT 120)
            endif()
            add_test(NAME real-model-long COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/tests/long_audio.py"
                "$<TARGET_FILE:mika-inference-test>" "${MIKA_TEST_MODEL}"
                "${transcribe_SOURCE_DIR}/samples/jfk.wav" ${punctuation_long_args})
            set_tests_properties(real-model-long PROPERTIES TIMEOUT 600)
        endif()
    endif()
endif()
