# Light-only theme trial

The app now always uses its existing light palette. The header toggle and legacy theme controller are no longer loaded. `static/light-theme.js` sets the light theme and native browser control color scheme before styles render, regardless of system preferences or a previously saved dark-mode selection. Saved preferences are preserved for rollback.

Dark-mode CSS, `static/theme-init.js`, `static/theme.js` and the previous browser checks (`qa/workspace_dark_theme_check.py`) remain in the repository. The pre-trial state is tagged `dark-mode-before-light-trial-2026-11-12`.

To undo this trial, revert the light-only change commit and redeploy. This restores the header toggle, original initialization and controller, and original style checks without reverting other app work. The preserved dark-mode check is intended for the restored version. `qa/light_theme_check.py` verifies the current trial.
