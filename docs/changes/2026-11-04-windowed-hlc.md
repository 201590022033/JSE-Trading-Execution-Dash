# Source-specific HLC research windows

The historical technical view now calculates ATR and prior high/low ranges
from the observed high, low and close fields they actually require. An invalid
or missing open is still reported as an OHLC defect and is never repaired or
admitted to a full-bar replay on this basis. Invalid HLC and source transitions
still delimit ATR windows. Diagnostics report both OHLC and HLC defects, plus
the ATR source, source hash, actual acquisition time and session bounds.

On the retained 2 November Sasol Yahoo history this makes ATR and the 20-session
range available despite 120 invalid OHLC rows, all of which had usable HLC.
Bidvest and BAT have valid HLC ranges but only four recent rows after their
IRESS-to-Yahoo transition, so same-source ATR remains unavailable in the joined
view. The evidence is retrospective and provider basis remains unverified.

ShareData SENS is supported, but the existing Zebra price panel lists IRESS,
Yahoo and OST. A usable ShareData historical OHLCV export has not been verified;
it must not be represented as a price source until acquired and checked.
