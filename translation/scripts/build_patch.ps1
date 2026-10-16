param([string]$SourcePaks = '', [string]$RetocPath = '', [string]$RepakPath = '', [switch]$CurrentTranslations)
# ============================================================
# 천사의 시 한글 패치 원클릭 빌드 스크립트
# 실행: powershell -ExecutionPolicy Bypass -File scripts\build_patch.ps1
# (작업 기준 폴더 = 이 스크립트의 상위 폴더 = translation)
# ============================================================
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot            # translation 폴더
$scripts = $PSScriptRoot
$retoc = (Resolve-Path -LiteralPath $RetocPath).Path
$repak = (Resolve-Path -LiteralPath $RepakPath).Path
$paksDir = (Resolve-Path -LiteralPath $SourcePaks).Path
$work = Join-Path $root "work"
$srcDir = Join-Path $work "src"             # 원본 legacy 추출본
$patchDir = Join-Path $work "patch_src"     # 패치 적용본 (to-zen 입력)
$outDir = Join-Path $work "out"             # 빌드 결과
$backup = Join-Path $root "백업_csv"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ------------------------------------------------------------

function Assert-IsolatedBuildWork([string]$path) {
    $expected = [IO.Path]::GetFullPath((Join-Path $root 'work')).TrimEnd('\')
    $actual = [IO.Path]::GetFullPath($path).TrimEnd('\')
    if ($actual -cne $expected) { throw 'Build work path outside expected directory' }
    if (Test-Path -LiteralPath $path) {
        $items = @((Get-Item -LiteralPath $path -Force)) + @(Get-ChildItem -LiteralPath $path -Force -Recurse)
        if (@($items | Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 }).Count -ne 0) { throw 'Reparse point in build work directory' }
    }
}
Assert-IsolatedBuildWork $work
Step "0. 작업 폴더 초기화"
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force -Path $srcDir, $patchDir, $outDir | Out-Null

# ------------------------------------------------------------
Step "1. XLSX -> CSV (3줄초과 수정본 자동 병합)"
python (Join-Path $scripts "xlsx_to_csv.py") $root (Join-Path $work "tenshi_master.csv")
if ($LASTEXITCODE -ne 0) { throw "xlsx_to_csv 실패" }

# UI/크레딧/선택화면: 루트에 xlsx가 있으면 그걸 쓰고, 없으면 백업_csv의 CSV 사용
$uiCsv = Join-Path $backup "ui_menu_text_paired.csv"
if (Test-Path (Join-Path $root "ui_menu_text_paired.xlsx")) {
    $uiCsv = Join-Path $work "ui_menu_text_paired.csv"
    python (Join-Path $scripts "xlsx2csv_any.py") (Join-Path $root "ui_menu_text_paired.xlsx") $uiCsv
    if ($LASTEXITCODE -ne 0) { throw "ui xlsx 변환 실패" }
}
$vsCsv = Join-Path $backup "visualscene_paired.csv"
if (Test-Path (Join-Path $root "visualscene_paired.xlsx")) {
    $vsCsv = Join-Path $work "visualscene_paired.csv"
    python (Join-Path $scripts "xlsx2csv_any.py") (Join-Path $root "visualscene_paired.xlsx") $vsCsv
    if ($LASTEXITCODE -ne 0) { throw "visualscene xlsx 변환 실패" }
}
$stCsv = Join-Path $backup "outgameinfo_paired.csv"
if (Test-Path (Join-Path $root "outgameinfo_paired.csv")) {
    $stCsv = Join-Path $root "outgameinfo_paired.csv"
} elseif (Test-Path (Join-Path $root "outgameinfo_paired.xlsx")) {
    $stCsv = Join-Path $work "outgameinfo_paired.csv"
    python (Join-Path $scripts "xlsx2csv_any.py") (Join-Path $root "outgameinfo_paired.xlsx") $stCsv
    if ($LASTEXITCODE -ne 0) { throw "outgameinfo xlsx 변환 실패" }
}

# ------------------------------------------------------------
Step "2. 원본 pak에서 대상 애셋 추출 (retoc to-legacy)"
& $retoc to-legacy -f "Localization" --version UE5_4 $paksDir $srcDir | Out-Null
& $retoc to-legacy -f "Data/DT" --version UE5_4 $paksDir $srcDir | Out-Null
& $retoc to-legacy -f "Ogix/WBP/Common/InGame" --version UE5_4 $paksDir $srcDir | Out-Null
$content = Join-Path $srcDir "Emulator_Tenshinouta\Content"
if (-not (Test-Path "$content\Localization\TextData\tenshi_text_en.uexp")) { throw "원본 추출 실패" }

# ------------------------------------------------------------
Step "3. 원본 문자열 스캔 (offset 지도 생성)"
python (Join-Path $scripts "extract_strings.py") "$content\Localization\TextData\tenshi_text_en.uexp" (Join-Path $work "tenshi_strings.json") (Join-Path $work "tenshi_strings.csv")
python (Join-Path $scripts "extract_strings.py") "$content\Localization\TextData\DT_Tenshi_VisualSceneText.uexp" (Join-Path $work "vs_strings.json") (Join-Path $work "vs_strings.csv")

# ------------------------------------------------------------
Step "4. 한국어 자동 줄바꿈 (전각 32자, 문자형 \n 정규화)"
python (Join-Path $scripts "rewrap_ko.py") (Join-Path $work "tenshi_master.csv") (Join-Path $work "tenshi_wrapped.csv")

# ------------------------------------------------------------
Step "5. 교체 계획(replacements) 생성"
python (Join-Path $scripts "build_replacements.py") tenshi (Join-Path $work "tenshi_strings.json") (Join-Path $work "tenshi_wrapped.csv") (Join-Path $work "repl_tenshi.json")
python (Join-Path $scripts "build_replacements.py") visualscene (Join-Path $work "vs_strings.json") $vsCsv (Join-Path $work "repl_vs.json")
python (Join-Path $scripts "build_ui_replacements.py") $srcDir $uiCsv (Join-Path $work "repl_ui.json")
python (Join-Path $scripts "build_st_replacements.py") "$content\Localization\DataTable_Game1\ST_OutGameInfo_Game1.uexp" $stCsv (Join-Path $work "repl_st.json")

# ------------------------------------------------------------
if (-not $CurrentTranslations) {
    foreach ($plan in @('repl_tenshi.json', 'repl_vs.json', 'repl_ui.json', 'repl_st.json')) {
        Copy-Item -LiteralPath (Join-Path $root "../assets/release_plans/$plan") -Destination (Join-Path $work $plan) -Force
    }
}
Step "6. 바이너리 패치 적용 (uexp 문자열 교체 + uasset SerialSize 갱신)"
# 대상 파일별 원본 SerialSize / SerialOffset (변하지 않는 상수)
$targets = @(
    @{ rel = "Localization\TextData\tenshi_text_en";                          repl = "repl_tenshi.json"; filter = $null;                                                        ss = 1389054; so = 100708 },
    @{ rel = "Localization\TextData\DT_Tenshi_VisualSceneText";               repl = "repl_vs.json";     filter = $null;                                                        ss = 29496;   so = 3635 },
    @{ rel = "Localization\DataTable_Game1\ST_OutGameInfo_Game1";             repl = "repl_st.json";     filter = $null;                                                        ss = 2803;    so = 703 },
    @{ rel = "L10N\en\Ogix\Data\DT\Common\DT_BootView";                       repl = "repl_ui.json";     filter = "L10N/en/Ogix/Data/DT/Common/DT_BootView.uexp";               ss = 335;     so = 1290 },
    @{ rel = "L10N\en\Ogix\Data\DT\Game_1\DT_Game1_GameInfo";                 repl = "repl_ui.json";     filter = "L10N/en/Ogix/Data/DT/Game_1/DT_Game1_GameInfo.uexp";         ss = 454;     so = 1074 },
    @{ rel = "L10N\en\Ogix\Data\DT\Game_1\DT_Game1_HomeMenuSelectInfo";       repl = "repl_ui.json";     filter = "L10N/en/Ogix/Data/DT/Game_1/DT_Game1_HomeMenuSelectInfo.uexp"; ss = 296;   so = 1217 },
    @{ rel = "L10N\en\Ogix\Data\DT\Game_1\DT_Game1_SoundInfo";                repl = "repl_ui.json";     filter = "L10N/en/Ogix/Data/DT/Game_1/DT_Game1_SoundInfo.uexp";        ss = 1588;    so = 4125 },
    @{ rel = "L10N\en\Ogix\Data\DT\Game_1\DT_Game1_VisualInfo";               repl = "repl_ui.json";     filter = "L10N/en/Ogix/Data/DT/Game_1/DT_Game1_VisualInfo.uexp";       ss = 254;     so = 3068 },
    @{ rel = "Ogix\Data\DT\Common\DT_BootView";                               repl = "repl_ui.json";     filter = "Ogix/Data/DT/Common/DT_BootView.uexp";                       ss = 335;     so = 1274 }
)
foreach ($t in $targets) {
    $srcUexp = Join-Path $content "$($t.rel).uexp"
    $srcUasset = Join-Path $content "$($t.rel).uasset"
    $dstUexp = Join-Path $patchDir "Emulator_Tenshinouta\Content\$($t.rel).uexp"
    $dstUasset = Join-Path $patchDir "Emulator_Tenshinouta\Content\$($t.rel).uasset"
    New-Item -ItemType Directory -Force -Path (Split-Path $dstUexp) | Out-Null

    $repl = Join-Path $work $t.repl
    if ($t.rel -eq "Localization\TextData\DT_Tenshi_VisualSceneText") {
        # 비주얼신 큐 타이밍은 원본 값을 유지한다. 한국어 자막 교체만 적용한다.
        python (Join-Path $scripts "apply_replacements.py") $srcUexp $repl $dstUexp
        if ($LASTEXITCODE -ne 0) { throw "visualscene 한글 패치 실패" }
        $newSerial = (Get-Item $dstUexp).Length - 4
        python (Join-Path $scripts "patch_serialsize_binary.py") $srcUasset $t.ss $t.so $newSerial $dstUasset
        if ($LASTEXITCODE -ne 0) { throw "visualscene SerialSize 패치 실패" }
        Write-Host "  OK: $($t.rel) (full Korean, original timing)"
        continue
    }
    if ($t.filter) {
        python (Join-Path $scripts "apply_replacements.py") $srcUexp $repl $dstUexp $t.filter
    } else {
        python (Join-Path $scripts "apply_replacements.py") $srcUexp $repl $dstUexp
    }
    if ($LASTEXITCODE -ne 0) { throw "uexp 패치 실패: $($t.rel)" }

    $newSerial = (Get-Item $dstUexp).Length - 4
    python (Join-Path $scripts "patch_serialsize_binary.py") $srcUasset $t.ss $t.so $newSerial $dstUasset
    if ($LASTEXITCODE -ne 0) { throw "SerialSize 패치 실패: $($t.rel)" }
    Write-Host "  OK: $($t.rel)"
}

$richSrc = Join-Path $content "Ogix\Data\DT\Common\DT_RichTextFormat"
$richDst = Join-Path $patchDir "Emulator_Tenshinouta\Content\Ogix\Data\DT\Common\DT_RichTextFormat"
New-Item -ItemType Directory -Force -Path (Split-Path "$richDst.uexp") | Out-Null
Copy-Item "$richSrc.uasset" "$richDst.uasset" -Force
python (Join-Path $scripts "patch_richtext_font_size.py") "$richSrc.uexp" "$richDst.uexp" 27.0 22.0 6
if ($LASTEXITCODE -ne 0) { throw "RichText font size 패치 실패" }
Write-Host "  OK: Ogix\Data\DT\Common\DT_RichTextFormat (font size 22 - 대화창 기본 크기와 일치)"

# 대화창(메시지 윈도우) 기본 폰트 크기: WBP_LocalizeText 우버그래프 바이트코드의
# EX_FloatConst 27.0(uexp 890, 0x1E 확인)이 K2Node_MakeStruct_SlateFontInfo로 적용된다.
# DT_RichTextFormat은 태그 스타일용이라 기본 크기에는 반영되지 않는다(실기 확인).
# 참고: uexp 4908의 LineHeightPercentage(1.3) 치환은 실기에서 줄 간격에 반영되지 않아 원복함 (2026-07-05)
$localizeTextSrc = Join-Path $content "Ogix\WBP\Common\InGame\Localize\WBP_LocalizeText"
$localizeTextDst = Join-Path $patchDir "Emulator_Tenshinouta\Content\Ogix\WBP\Common\InGame\Localize\WBP_LocalizeText"
New-Item -ItemType Directory -Force -Path (Split-Path "$localizeTextDst.uexp") | Out-Null
Copy-Item "$localizeTextSrc.uasset" "$localizeTextDst.uasset" -Force
python (Join-Path $scripts "patch_floats_at_offsets.py") "$localizeTextSrc.uexp" "$localizeTextDst.uexp" "890:27:22"
if ($LASTEXITCODE -ne 0) { throw "LocalizeText 대화창 폰트 크기 패치 실패" }
Write-Host "  OK: Ogix\WBP\Common\InGame\Localize\WBP_LocalizeText (대화창 크기 22)"

# DT_LocalizeTextStyle / WBP_EnglishSubtitles 크기 패치는 실기 확인 결과 비주얼신 자막에 반영되지 않아 원복 (2026-07-05)
Write-Host "  SKIP: DT_LocalizeTextStyle (원본 22 유지)"
Write-Host "  SKIP: WBP_EnglishSubtitles (원본 40 유지)"

# WBP_VisualSceneText는 절대 전역 float 치환(patch_richtext_font_size.py) 패치하지 말 것.
# 이 uexp의 32.0f 매치는 폰트 크기가 아니라 "BPTYPE_Normal" FString의 길이 필드+첫 글자('B'=0x42)에
# 걸친 우연한 바이트 패턴이라, 치환하면 문자열 길이가 0xC000000E로 깨져 로딩 프리징이 발생한다.
# 이 위젯에는 직렬화된 폰트 크기가 없고, 구조는 960x200 박스(SizeBox/슬롯) -> ScaleBox -> RichTextBlock.
# ScaleBox가 텍스트를 박스에 맞춰 스케일하므로 폰트 크기(DT_LocalizeTextStyle)는 화면 크기에 반영되지 않는다.
# 비주얼신 자막 크기: RichTextBlock의 DefaultTextStyleOverride(bOverrideDefaultStyle=true, 색상 프로브로
# 실사용 확인)에 FSlateFontInfo.Size가 직렬화되어 있지 않아 어떤 폰트 크기 패치도 무효였다.
# inject_visualscene_fontsize.py가 unversioned fragment를 수정해 Size 필드를 직접 주입한다.
$visualSceneWbpSrc = Join-Path $content "Ogix\WBP\Common\InGame\Localize\WBP_VisualSceneText"
$visualSceneWbpDst = Join-Path $patchDir "Emulator_Tenshinouta\Content\Ogix\WBP\Common\InGame\Localize\WBP_VisualSceneText"
New-Item -ItemType Directory -Force -Path (Split-Path "$visualSceneWbpDst.uexp") | Out-Null
python (Join-Path $scripts "inject_visualscene_fontsize.py") "$visualSceneWbpSrc.uexp" "$visualSceneWbpSrc.uasset" "$visualSceneWbpDst.uexp" "$visualSceneWbpDst.uasset" 16.5
if ($LASTEXITCODE -ne 0) { throw "VisualSceneText 폰트 Size 주입 실패" }
Write-Host "  OK: Ogix\WBP\Common\InGame\Localize\WBP_VisualSceneText (font Size 16.5 주입 = 체감 22)"

# 대화창 페이징 커서(삼각형)는 WBP_Paging 자체에서 Hidden으로 고정한다.
# - WBP_Paging 브러시 ImageSize 0: 실기 무효(위치·크기를 네이티브 코드가 결정)
# - message_button 텍스처 투명화: 텍스처 주입 후 게임이 실행되지 않아 원복 (2026-07-05)
#   (컨테이너 마운트는 되나 부팅 중 크래시. 원인 미확정)
$pagingSrc = Join-Path $content "Ogix\WBP\Common\InGame\Localize\WBP_Paging"
$pagingDst = Join-Path $patchDir "Emulator_Tenshinouta\Content\Ogix\WBP\Common\InGame\Localize\WBP_Paging"
New-Item -ItemType Directory -Force -Path (Split-Path "$pagingDst.uexp") | Out-Null
python (Join-Path $scripts "patch_paging_cursor_visibility.py") "$pagingSrc.uexp" "$pagingSrc.uasset" "$pagingDst.uexp" "$pagingDst.uasset"
if ($LASTEXITCODE -ne 0) { throw "WBP_Paging 커서 숨김 패치 실패" }
Write-Host "  OK: WBP_Paging 커서 Hidden 적용"

# to-zen에 필요한 스크립트 오브젝트 복사
Copy-Item (Join-Path $srcDir "scriptobjects.bin") $patchDir -Force

# ------------------------------------------------------------
if (-not $CurrentTranslations) {
    $manualAssetRoot = Join-Path $root 'manual_patch_assets'
    if (-not (Test-Path -LiteralPath $manualAssetRoot)) { throw 'Run prepare_build_inputs.py first; frozen manual assets are required' }
    foreach ($asset in (Get-ChildItem -LiteralPath $manualAssetRoot -Recurse -File)) {
        $relative = $asset.FullName.Substring($manualAssetRoot.Length + 1)
        $destination = Join-Path $patchDir $relative
        New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
        Copy-Item -LiteralPath $asset.FullName -Destination $destination -Force
    }
}
Step "6.5 매뉴얼 이미지 주입 (매뉴얼_번역\*.png 있을 때만)"
$manualPng = Join-Path $root "매뉴얼_번역"
if ($CurrentTranslations -and (Test-Path $manualPng) -and (Get-ChildItem $manualPng -Filter "Manual1_*.png" -ErrorAction SilentlyContinue)) {
    $manualSrc = Join-Path $work "manual_src"
    New-Item -ItemType Directory -Force -Path $manualSrc | Out-Null
    & $retoc to-legacy -f "ManualBook" --version UE5_4 $paksDir $manualSrc | Out-Null
    python (Join-Path $scripts "inject_manual_png.py") $manualSrc $manualPng $patchDir
    if ($LASTEXITCODE -ne 0) { throw "매뉴얼 주입 실패" }
} else {
    Write-Host "  (매뉴얼 PNG 없음 - 건너뜀)"
}

# ------------------------------------------------------------
Step "7. Zen 컨테이너 빌드 (retoc to-zen)"
& $retoc to-zen --version UE5_4 $patchDir (Join-Path $outDir "TenshiKR_P.utoc") | Out-Null
if (-not (Test-Path (Join-Path $outDir "TenshiKR_P.ucas"))) { throw "to-zen 실패" }

# ------------------------------------------------------------
Step "8. patch_P 폴더로 배포"
$deploy = Join-Path $root "patch_P"
New-Item -ItemType Directory -Force -Path $deploy | Out-Null
Copy-Item (Join-Path $outDir "TenshiKR_P.pak") $deploy -Force
Copy-Item (Join-Path $outDir "TenshiKR_P.ucas") $deploy -Force
Copy-Item (Join-Path $outDir "TenshiKR_P.utoc") $deploy -Force

Step "8.5 낮은 세로 메트릭 폰트 pak 생성"
$fontSrc = Join-Path $root "fontsrc_condensed"
$fontWork = Join-Path $work "fontsrc_lowmetrics"
if (-not (Test-Path $fontSrc)) { throw "폰트 소스 폴더 없음: $fontSrc" }
if (Test-Path $fontWork) { Remove-Item -Recurse -Force $fontWork }
Copy-Item $fontSrc $fontWork -Recurse -Force
$fontDir = Join-Path $fontWork "Emulator_Tenshinouta\Content\Ogix\Font"
python (Join-Path $scripts "patch_font_vertical_metrics.py") (Join-Path $fontSrc "Emulator_Tenshinouta\Content\Ogix\Font\k8x12.ufont") (Join-Path $fontDir "k8x12.ufont") --factor 1.08 --desc-factor 0.16
if ($LASTEXITCODE -ne 0) { throw "k8x12 폰트 세로 메트릭 패치 실패" }
python (Join-Path $scripts "patch_font_vertical_metrics.py") (Join-Path $fontSrc "Emulator_Tenshinouta\Content\Ogix\Font\BIZUDGothic-Regular.ufont") (Join-Path $fontDir "BIZUDGothic-Regular.ufont") --factor 1.08 --desc-factor 0.16
if ($LASTEXITCODE -ne 0) { throw "BIZUDGothic 폰트 세로 메트릭 패치 실패" }
& $repak pack --version V11 -p 1253859140 $fontWork (Join-Path $deploy "TenshiKR_Font_P.pak") | Out-Null
if ($LASTEXITCODE -ne 0) { throw "폰트 pak 생성 실패" }
if (-not (Test-Path (Join-Path $deploy "TenshiKR_Font_P.pak"))) { throw "폰트 pak 출력 없음" }

Get-ChildItem $deploy | Format-Table Name, Length, LastWriteTime -AutoSize

Write-Host "Build complete. Outputs remain in translation/patch_P; no emulator deployment."
