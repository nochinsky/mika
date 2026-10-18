# One fixed formatter, not a backend registry. Preparation and payload layout
# are deliberately unchanged; --raw bypasses loading it at runtime.
if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR
   NOT ((APPLE AND CMAKE_SYSTEM_PROCESSOR MATCHES "^(arm64|aarch64)$") OR
        ((WIN32 OR CMAKE_SYSTEM_NAME STREQUAL "Linux") AND
         CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$")))
    message(FATAL_ERROR "Mika supports Linux/Windows x86-64 and experimental macOS arm64")
endif()
find_package(Python3 3.12 REQUIRED COMPONENTS Interpreter)
if(WIN32)
    set(punctuation_platform windows)
elseif(APPLE)
    set(punctuation_platform macos)
else()
    set(punctuation_platform linux)
endif()
set(punctuation_stage "${CMAKE_BINARY_DIR}/_deps/punctuation")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/fetch_punctuation.py"
    --stage "${punctuation_stage}" --platform "${punctuation_platform}"
    COMMAND_ERROR_IS_FATAL ANY)
# Self-contained SentencePiece avoids newer upstream's automatic Abseil checkout.
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
elseif(APPLE)
    set_target_properties(mika_ort PROPERTIES IMPORTED_LOCATION "${punctuation_stage}/payload/libonnxruntime.dylib")
else()
    set_target_properties(mika_ort PROPERTIES IMPORTED_LOCATION "${punctuation_stage}/payload/libonnxruntime.so")
endif()
add_library(mika-fullstop SHARED src/fullstop.cpp)
target_compile_definitions(mika-fullstop PRIVATE MIKA_FULLSTOP_BUILD=1)
target_include_directories(mika-fullstop SYSTEM PRIVATE
    "${punctuation_stage}/include" "${sentencepiece_SOURCE_DIR}/src")
target_link_libraries(mika-fullstop PRIVATE mika_fullstop_render sentencepiece-static mika_ort)
set_target_properties(mika-fullstop PROPERTIES CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
if(APPLE)
    set_target_properties(mika-fullstop PROPERTIES
        BUILD_WITH_INSTALL_RPATH TRUE INSTALL_RPATH "@loader_path")
elseif(UNIX)
    set_target_properties(mika-fullstop PROPERTIES BUILD_WITH_INSTALL_RPATH TRUE INSTALL_RPATH "$ORIGIN")
    target_link_options(mika-fullstop PRIVATE "LINKER:--exclude-libs,ALL")
endif()
mika_warnings(mika-fullstop)
add_library(mika_punctuation STATIC src/punctuation_backend.cpp)
target_link_libraries(mika_punctuation PUBLIC mika_punctuation_guard mika_model ${CMAKE_DL_LIBS})
mika_warnings(mika_punctuation)
if(MSVC)
    # Retain a defensive boundary even for an unexpectedly throwing module.
    # /EHsc's extern-C-is-nothrow assumption must not remove the catch.
    target_compile_options(mika_punctuation PRIVATE /EHsc-)
endif()
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
