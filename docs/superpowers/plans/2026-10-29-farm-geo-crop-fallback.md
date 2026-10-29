# Farm geo + leaf crop fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** State/GPS-driven soil+crop defaults on farm profile; leaf diagnosis uses profile crop when unset/undetected.

**Architecture:** Static `indiaFarmDefaults` on the frontend; Nominatim/BigDataCloud reverse geocode for GPS; orchestrator passes `farm_profile_crop` as vision `crop_hint` when user did not pick a crop.

**Tech Stack:** React + TypeScript frontend, FastAPI orchestrator.

## Tasks

1. Add `frontend/src/lib/indiaFarmDefaults.ts` (states, soil, crops, parse/build location).
2. Add `reverseGeocodeIndianState(lat, lon)` helper (BigDataCloud client API).
3. Update `FarmProfileForm` UI + i18n keys.
4. Update `ChatInput` to preselect profile crop on image attach.
5. Orchestrator: `crop_hint = user_selected_crop or farm_profile_crop`.
6. `npx tsc --noEmit` + quick manual checklist.
