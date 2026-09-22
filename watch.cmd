@echo off
rem Bring the OCP CAD Viewer up and keep it showing the current CAD, finished.
rem
rem   watch.cmd                     the whole robot, redrawn every time you save
rem   watch.cmd pelvis-shell        one printed piece, on its own
rem   watch.cmd torso-packing-check a check scene, with its groups named
rem   watch.cmd --raw               as modelled, sharp arrises, which is faster
rem   watch.cmd --size 2            an exaggerated chamfer, to SEE it is there
rem   watch.cmd --list              what can be shown
rem   watch.cmd --browser          a standalone viewer in a browser tab
rem
rem IT SHOWS THE FINISHED DESIGN unless you ask for --raw. The parts leave
rem cad/ with sharp arrises and the 0.5 mm chamfer is a separate pass in
rem cad/finish.py, so what the viewer drew until now was the part as modelled
rem rather than the part as printed. This adds --finished for you.
rem
rem What that costs, and what to do about it. Every printed piece goes through
rem the chamfer on every redraw, which is about a minute for the whole robot and
rem a fraction of a second for one piece -- so name the piece you are working on
rem while you are working on edges, or pass --raw when the shape rather than the
rem finish is the question. And at 0.5 mm the chamfer is about three pixels wide
rem at a zoom that fits a whole limb: --size 2 exaggerates it, at the price of a
rem few edges OCCT then refuses to cut at all.
rem
rem Everything you pass goes through to tools/view.py, which is what draws. The
rem work is all in tools/watch.py, which redraws on every save.
rem
rem IT DRAWS INTO VS CODE, AND CTRL-SHIFT-B IS THE WHOLE GESTURE. That is the
rem "watch the CAD" task in .vscode/tasks.json: it opens the OCP CAD Viewer panel
rem and then runs this against it. By hand it is two steps -- ctrl-shift-P,
rem "OCP CAD Viewer: Open viewer", then this -- and in either order, because
rem until a viewer exists this waits for one rather than drawing a robot it has
rem nowhere to put.
rem
rem WHICH PORT THE PANEL IS ON IS NOT ASSUMED. 3939 is only where the extension
rem starts looking for a free one, so a standalone viewer or a second window puts
rem the panel on 3940 and up. Every viewer registers itself in ~/.ocpvscode and
rem tools/watch.py reads that, so it finds the panel wherever it landed.
rem
rem --browser is the other way: a standalone viewer in a browser tab, started
rem here and stopped again when you stop watching.
rem
rem Free and offline, like everything else here: the geometry is tessellated on
rem this machine and pushed to the viewer over a socket.
setlocal
pushd "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not on PATH. It is what runs everything in this repository:
    echo   https://docs.astral.sh/uv/
    popd
    exit /b 1
)

rem --raw and --browser are this script's own flags and view.py knows nothing
rem about either, so they are taken out of the arguments rather than passed on.
rem Everything else goes through untouched, quoting and all, which is why this is
rem a shift loop and not a for over %* -- that one splits on commas and expands
rem wildcards.
set "FINISH=--finished"
set "SERVE="
set "ARGS="
:parse
if "%~1"=="" goto run
if /I "%~1"=="--raw" (
    set "FINISH="
) else if /I "%~1"=="--browser" (
    set "SERVE=--serve"
) else (
    set "ARGS=%ARGS% %1"
)
shift
goto parse

:run
uv run tools/watch.py %SERVE% %FINISH%%ARGS%
set WATCH_EXIT=%ERRORLEVEL%
popd
exit /b %WATCH_EXIT%
