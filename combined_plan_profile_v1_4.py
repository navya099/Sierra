"""Sierra root compatibility launcher for isolated v1.4.2 package."""
import runpy
if __name__ == "__main__":
    runpy.run_module("combined_plan_profile.combined_plan_profile_v1_4", run_name="__main__")
