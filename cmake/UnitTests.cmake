# Shared ML-free tests of real runtime policy. Fake APIs are deliberately local
# to this target; production/full builds still compile against pinned upstream.
add_executable(mika-engine-unit "${MIKA_SOURCE_DIR}/src/engine.c" "${MIKA_SOURCE_DIR}/tests/engine_unit.c")
target_include_directories(mika-engine-unit PRIVATE "${MIKA_SOURCE_DIR}/tests/fake-transcribe")
target_link_libraries(mika-engine-unit PRIVATE mika_platform)
mika_warnings(mika-engine-unit)
add_test(NAME engine-unit COMMAND mika-engine-unit)
add_executable(mika-assets-unit "${MIKA_SOURCE_DIR}/tests/assets_unit.cpp")
target_link_libraries(mika-assets-unit PRIVATE mika_assets)
mika_warnings(mika-assets-unit)
add_test(NAME assets-unit COMMAND mika-assets-unit)
set_tests_properties(engine-unit assets-unit PROPERTIES TIMEOUT 30)
