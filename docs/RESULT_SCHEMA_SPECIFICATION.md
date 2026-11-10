# Soma scientific result schema specification

Schema name `soma.result`, current schema version `1.1.0`, software Soma0.17.0.
The runtime validator is `soma.sdk.results.validate_result`. Version1.0.0 is a
constructed compatibility baseline introduced in this milestone, not a claim that
old core manifest schema_version=1 was this format. Legacy formats need adapters.

## Shared envelope

Required: schema_name, schema_version, producer, producer_version, result_kind,
interpretation_state, provenance, payload, checksums. For native scientific kinds,
method{id,version}, parameters and units are also required. Optional fields are
created_at, dataset_identity, subject_identity, spatial_reference,
temporal_reference, statistical_estimand, warnings and migration. Unknown fields
fail. Omission means unrecorded/unknown; explicit null means known inapplicable.
Do not use null to conceal missing scientific information. Timestamp, when supplied,
is timezone-aware ISO8601; no historical timestamp is synthesized. Identity strings
are declarations, not permission to share participant information.

Payload has exactly domain, arrays and values. Domain fields are closed per family.
Arrays map explicit names to file, dtype, shape, content_sha256. Relative file names
are exactly arrays/NAME.npy. Values contains small strict finite JSON summaries;
undefined metrics can be null. Numerical arrays belong outside JSON. Checksums
contains a metadata SHA256 and a mapping of per-array file-byte SHA256 values.
The metadata digest is canonical sorted compact JSON excluding its own digest.
Array content digests include dtype, shape and C-order bytes, reusing the SDK's
existing array_fingerprint. A checksum is integrity evidence, not authentication.

## Families and meanings

| Result kind | Required domain declarations / arrays |
|---|---|
| eeg.spectrum | fs_hz, channels, reference, window, psd_config; frequencies(Hz), density(channel×frequency). Config fixes segment/overlap/window/average/density/one-sided. |
| eeg.time_frequency | sampling/channels/reference/window/tf_config; frequencies, times, power(trial×channel×frequency×time), Boolean valid mask(frequency×time). |
| eeg.bursts | sampling/channels/reference/window, explicit low/high/minimum-duration/calibration/filter thresholds, half-open seconds; start/stop intervals. |
| mri.geometry | image identity, shape, affine, spacing, grid identity; explicit spatial frame/space/unit. |
| mri.segmentation | image/grid identity, ontology, label correspondence, boundary definition; metric values retain their declared units. |
| mri.surface | geometry identity, frame, surface semantics; optional recorded topology checks. |
| mri.registration | fixed/moving identity, reference_to_source pull direction, frame; 4×4 transform. |
| source.reconstruction | source/forward/inverse identities, regularization, conductivities(S/m), anatomical readiness and resolution definition; amplitude(source×sample). |
| fmri.contrast | subject/session/task/run, TR, design identity, contrast weights, noise, inference policy, correction, preprocessing, spatial reference and estimand. |
| fmri.roi | contrast fields plus ROI ontology/space. Summary uncertainty remains method-dependent. |
| experiment.manifest | computation, relative input hashes, environment, assumptions, validation checks and limitations. |
| legacy.record | explicit source format and missing metadata; full original JSON preserved in values and provenance; INDETERMINATE. |

MRI/source spatial references declare frame(RAS/LPS/HEAD/MRI/TEMPLATE_MRI), space,
unit(m/mm), optional grid identity. Existing Soma geometry remains RAS+ metres;
a schema may describe another convention but never transforms it implicitly.
Temporal references record known sampling/TR/time origin/window definition only.
EEG reference can be null only when explicitly inapplicable; incomplete migrated
EEG records can omit it under INDETERMINATE. Power density V²/Hz, wavelet power V²,
frequency Hz, time s, distance mm/m, area/volume squared/cubed and source A*m/nA*m
are distinct dimensions. BOLD/regressor and its squared variance are not volts.

Format checks include dimensions, cross-array axes, finite real numerical data,
unit dimensions, affine/spacing constraints and supported interpretation states.
Native NaN-edged wavelet arrays need an explicit supported finite/missingness
representation; the serializer never fills or discards samples automatically.
A schema cannot certify a montage, tissue label, conductivity, preprocessing
pipeline or statistical assumption. fMRI contracts must explicitly deny
confirmation; this subsystem does not fit models or expand the existing guard.
