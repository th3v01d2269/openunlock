package com.openunlock

/**
 * IMEI helpers — native port of openunlock/imei.py (luhn_valid,
 * _parse_iphonesubinfo, parse_service_call_imei). No IMEI value is ever
 * written anywhere: read/verify only, same as the CLI.
 */
object Imei {

    private val IMEI_RE = Regex("\\d{15}")

    /** Luhn check for a 15-digit IMEI (last digit is the check digit). */
    fun luhnValid(number: String?): Boolean {
        if (number == null || !number.matches(Regex("\\d{15}"))) return false
        var total = 0
        for ((i, ch) in number.reversed().withIndex()) {
            var d = ch - '0'
            if (i % 2 == 1) {
                d *= 2
                if (d > 9) d -= 9
            }
            total += d
        }
        return total % 10 == 0
    }

    /** Extract IMEIs from `dumpsys iphonesubinfo` output. */
    fun parseDumpsys(output: String): List<String> {
        val found = ArrayList<String>()
        for (line in output.lines()) {
            if (line.contains(Regex("imei|device.?id|subscriber", RegexOption.IGNORE_CASE))) {
                found += IMEI_RE.findAll(line).map { it.value }
            }
        }
        if (found.isEmpty()) {
            found += IMEI_RE.findAll(output).map { it.value }.filter { luhnValid(it) }
        }
        return found.distinct()
    }

    /**
     * Parse `service call iphonesubinfo` parcel output into IMEI strings.
     * The service call prints a hex dump of the reply Parcel; the IMEI is
     * stored as a UTF-16 string. Reconstructs the parcel bytes from the
     * hex dump, decodes as UTF-16LE, and returns any Luhn-valid 15-digit
     * runs. Example line: 0x00000000: 00000000 0000000f 00330035 ...
     */
    fun parseServiceCall(output: String): List<String> {
        val words = ArrayList<Int>()
        val lineRe = Regex("0x[0-9a-fA-F]+:\\s+((?:[0-9a-fA-F]{8}\\s*)+)")
        for (line in output.lines()) {
            val m = lineRe.find(line) ?: continue
            for (w in m.groupValues[1].trim().split(Regex("\\s+"))) {
                words += w.toInt(16)
            }
        }
        if (words.isEmpty()) return emptyList()
        val raw = ByteArray(words.size * 4)
        for ((i, w) in words.withIndex()) {
            raw[i * 4] = (w and 0xFF).toByte()
            raw[i * 4 + 1] = ((w shr 8) and 0xFF).toByte()
            raw[i * 4 + 2] = ((w shr 16) and 0xFF).toByte()
            raw[i * 4 + 3] = ((w shr 24) and 0xFF).toByte()
        }
        val text = String(raw, Charsets.UTF_16LE)
        return IMEI_RE.findAll(text).map { it.value }
            .filter { luhnValid(it) }.distinct().toList()
    }
}
