from __future__ import annotations

from pathlib import Path

from .models import Candidate, Material
from .reporting import ContactPinStats


def _density_tonne_per_mm3(density_kg_m3: float) -> float:
    # 1 kg = 1e-3 tonne, 1 m^3 = 1e9 mm^3
    return density_kg_m3 * 1.0e-12


def write_ansys_static_template(
    *,
    path: Path,
    candidate: Candidate,
    material: Material,
    target_torque_nm: float,
    motor_speed_rpm: float,
    contact_stats: ContactPinStats,
) -> Path:
    dens_t_mm3 = _density_tonne_per_mm3(material.density_kg_m3)

    recommended_pins = 12
    if contact_stats.max_contact_pins >= 14:
        recommended_pins = 16
    elif contact_stats.max_contact_pins <= 8:
        recommended_pins = 10

    text = f"""! ============================================================
! Cycloidal Drive - ANSYS Static Structural Template (MAPDL)
! Auto-generated from cycloidal_geometry_solver.py
! Units: mm, N, s, MPa
! ============================================================

! ---------------------------
! Selected candidate summary
! ---------------------------
! stage_ratio                       = {candidate.stage_ratio}
! ring_pin_count                    = {candidate.ring_pin_count}
! lobe_count                        = {candidate.lobe_count}
! ring_pitch_diameter_mm            = {candidate.ring_pitch_diameter_mm}
! ring_roller_diameter_mm           = {candidate.ring_roller_diameter_mm}
! eccentricity_mm                   = {candidate.eccentricity_mm}
! disc_thickness_mm                 = {candidate.disc_thickness_mm}
! output_pin_count                  = {candidate.output_pin_count}
! output_roller_diameter_mm         = {candidate.output_roller_diameter_mm}
! target_output_torque_Nm           = {target_torque_nm}
! estimated_output_speed_rpm        = {candidate.estimated_output_speed_rpm}
! source_motor_speed_rpm            = {motor_speed_rpm}
!
! Estimated ring-pin contact (disc A):
! contact_band_mm                   = +/-{contact_stats.contact_band_mm}
! min/avg/max contact pins          = {contact_stats.min_contact_pins}/{contact_stats.avg_contact_pins:.2f}/{contact_stats.max_contact_pins}
! recommended ring pins for static  = {recommended_pins}
!
! Recommended model variant:
! - For fast static screening: use the "disc+pins+shaft" STEP and include ~{recommended_pins} pins around loaded zone.
! - For highest fidelity: use full assembly STEP and all pins.

/prep7

! ---------------------------
! Material (from solver)
! ---------------------------
mp,ex,1,{material.elastic_modulus_gpa * 1000.0:.6f}
mp,prxy,1,{material.poisson_ratio:.6f}
mp,dens,1,{dens_t_mm3:.12e}

! ---------------------------------------------------
! Geometry import note
! ---------------------------------------------------
! This template expects geometry to be imported in Workbench Mechanical.
! If running pure MAPDL, import external geometry first and mesh, then
! assign CM names below to matching regions.

! ---------------------------------------------------
! Named Selection / Component expectations
! ---------------------------------------------------
! CM,Housing, VOLU
! CM,Disc, VOLU
! CM,InputShaft, VOLU
! CM,OutputCarrier, VOLU
! CM,RingPins, VOLU
! CM,OutputPins, VOLU

! ---------------------------------------------------
! Contact setup guidance (create in Mechanical)
! ---------------------------------------------------
! 1) Disc <-> RingPins : Frictional or Frictionless contact
!    - Small sliding off, Large sliding on
!    - Program controlled normal stiffness, adjust if penetration persists
! 2) Disc output holes <-> OutputPins : Frictional/frictionless per study intent
! 3) Disc bore <-> eccentric journal : Frictional or bonded (for simplified static)

! ---------------------------------------------------
! Loads / boundary conditions guidance
! ---------------------------------------------------
! - Fix housing support faces (or remote displacement on housing mount)
! - Apply input torque on input shaft:
!   Tin = {target_torque_nm / max(candidate.stage_ratio,1):.6f} N*m   (approx from ratio)
! - Optionally verify output reaction torque near {target_torque_nm:.6f} N*m

! ---------------------------------------------------
! Solve placeholder
! ---------------------------------------------------
!/solu
!antype,static
!nlgeom,on
!solve
!finish

! ---------------------------------------------------
! Postprocessing placeholder
! ---------------------------------------------------
!/post1
!set,last
!plnsol,s,eqv
!prnsol,u,comp
"""
    path.write_text(text, encoding="utf-8")
    return path

