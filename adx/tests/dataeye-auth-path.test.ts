import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  ADX_PROJECT_ROOT,
  AUTH_DIR,
  LEGACY_STORAGE_STATE_PATH,
  STORAGE_STATE_PATH,
  resolveDataEyeStorageStatePath
} from "../src/dataeye/auth.js";

describe("DataEye storage state paths", () => {
  it("defaults to the shared repository auth state", () => {
    expect(STORAGE_STATE_PATH).toBe(resolve(AUTH_DIR, "dataeye-state.json"));
    expect(LEGACY_STORAGE_STATE_PATH).toBe(resolve(ADX_PROJECT_ROOT, ".auth/dataeye-state.json"));
  });

  it("resolves configured relative paths from the adx project root", () => {
    expect(resolveDataEyeStorageStatePath("../.auth/custom-state.json")).toBe(
      resolve(ADX_PROJECT_ROOT, "../.auth/custom-state.json")
    );
  });

  it("treats the old project-local default as a shared-state migration value", () => {
    expect(resolveDataEyeStorageStatePath(".auth/dataeye-state.json")).toBe(resolve(AUTH_DIR, "dataeye-state.json"));
  });
});
