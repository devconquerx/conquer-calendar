/**
 * Email domain autocorrection utility.
 * Corrects common typos in email providers (gmail, hotmail, outlook, etc.)
 * using a known-typo map + Levenshtein distance fuzzy matching.
 *
 * Ported from conquerx-funnels-new/src/utils/vsl-cb-typeform.js
 */

const KNOWN_PROVIDERS = [
  'gmail', 'hotmail', 'outlook', 'icloud', 'live', 'msn', 'yahoo',
  'protonmail', 'aol', 'zoho', 'gmx', 'yandex',
]

const VALID_TLDS = [
  // Generic
  'com', 'net', 'org', 'edu', 'gov', 'io', 'app', 'info', 'biz', 'me', 'tv', 'cc', 'xyz',
  // LATAM
  'ar', 'mx', 'pe', 'co', 'cl', 'br', 've', 'ec', 'uy', 'py', 'bo', 'cr', 'pa', 'gt', 'hn', 'sv', 'ni', 'do', 'cu', 'pr',
  // Europe
  'es', 'fr', 'de', 'nl', 'it', 'uk', 'pt', 'be', 'at', 'ch', 'pl', 'se', 'no', 'dk', 'fi', 'ie', 'gr', 'cz', 'ro', 'hu',
  // Other
  'us', 'ca', 'au', 'nz', 'jp', 'cn', 'kr', 'in', 'ru', 'za',
]

const KNOWN_TYPOS = {
  // Gmail
  'gamil': 'gmail', 'gmial': 'gmail', 'gemeil': 'gmail', 'giml': 'gmail',
  'gml': 'gmail', 'gmai': 'gmail', 'gmil': 'gmail', 'gmaill': 'gmail',
  'gnail': 'gmail', 'gemail': 'gmail', 'magil': 'gmail', 'gmaik': 'gmail',
  'gmaio': 'gmail', 'gmali': 'gmail', 'gmaul': 'gmail', 'gmeil': 'gmail',
  'gmayl': 'gmail', 'gmall': 'gmail', 'ggmail': 'gmail', 'gmmail': 'gmail',
  'gmaila': 'gmail', 'gmailc': 'gmail', 'hmail': 'gmail', 'fmail': 'gmail',
  'gail': 'gmail', 'gamail': 'gmail', 'gimail': 'gmail', 'gmsil': 'gmail',
  'gmqil': 'gmail', 'gmaim': 'gmail', 'gmaikl': 'gmail',
  'gmaol': 'gmail', 'gmale': 'gmail', 'gmaile': 'gmail', 'gmaiö': 'gmail',
  'mgail': 'gmail', 'gmailñ': 'gmail', 'gnmail': 'gmail', 'vmail': 'gmail',
  // Hotmail
  'hotmal': 'hotmail', 'hotmial': 'hotmail', 'hotmil': 'hotmail',
  'htomail': 'hotmail', 'hotamail': 'hotmail', 'hotmai': 'hotmail',
  'hotmall': 'hotmail', 'homail': 'hotmail', 'hotmeil': 'hotmail',
  'hotmaill': 'hotmail', 'hotmqil': 'hotmail', 'hotmsil': 'hotmail',
  'hitmail': 'hotmail', 'hatmail': 'hotmail', 'hutmail': 'hotmail',
  'jotmail': 'hotmail', 'gotmail': 'hotmail', 'hormail': 'hotmail',
  'hotmali': 'hotmail', 'hotmaik': 'hotmail', 'hotmaol': 'hotmail',
  'hotmaiñ': 'hotmail', 'hotamil': 'hotmail', 'hotmael': 'hotmail',
  'hotnail': 'hotmail', 'hotmaul': 'hotmail', 'hotmaikl': 'hotmail',
  // Outlook
  'outook': 'outlook', 'outlok': 'outlook', 'outllok': 'outlook',
  'outlool': 'outlook', 'outloock': 'outlook', 'outluk': 'outlook',
  'outlock': 'outlook', 'oulook': 'outlook', 'oitlook': 'outlook',
  'putlook': 'outlook', 'iutlook': 'outlook', 'ourlook': 'outlook',
  'outlooj': 'outlook', 'outlokk': 'outlook', 'outloik': 'outlook',
  'outloog': 'outlook', 'outlppk': 'outlook', 'outlokc': 'outlook',
  // iCloud
  'iclud': 'icloud', 'iclod': 'icloud', 'icoud': 'icloud',
  'iclould': 'icloud', 'iclooud': 'icloud', 'iclou': 'icloud',
  'icluod': 'icloud', 'iclouc': 'icloud', 'icload': 'icloud',
  'iclaud': 'icloud', 'icluoud': 'icloud', 'icloudd': 'icloud',
  'iclouf': 'icloud', 'icloid': 'icloud', 'ixloud': 'icloud',
  // Yahoo
  'yaho': 'yahoo', 'yahooo': 'yahoo', 'yhoo': 'yahoo', 'yhaoo': 'yahoo',
  'yaoo': 'yahoo', 'yahho': 'yahoo', 'yahooi': 'yahoo', 'yahool': 'yahoo',
  'yqhoo': 'yahoo', 'yshoo': 'yahoo', 'yahpp': 'yahoo', 'yahhoo': 'yahoo',
  'yah00': 'yahoo', 'yaboo': 'yahoo', 'yanoo': 'yahoo', 'yahoi': 'yahoo',
  // Live
  'liv': 'live', 'livee': 'live', 'liive': 'live', 'ive': 'live',
  // ProtonMail
  'protonmal': 'protonmail', 'protonmial': 'protonmail', 'protonmil': 'protonmail',
  'protonmaill': 'protonmail', 'protonmai': 'protonmail', 'protonmali': 'protonmail',
  'protonmeil': 'protonmail', 'protommail': 'protonmail', 'protonmmail': 'protonmail',
}

function levenshteinDistance(str1, str2) {
  const m = str1.length
  const n = str2.length
  const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))

  for (let i = 0; i <= m; i++) dp[i][0] = i
  for (let j = 0; j <= n; j++) dp[0][j] = j

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (str1[i - 1] === str2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1]
      } else {
        dp[i][j] = Math.min(dp[i - 1][j - 1] + 1, dp[i - 1][j] + 1, dp[i][j - 1] + 1)
      }
    }
  }
  return dp[m][n]
}

function similarityPercentage(str1, str2) {
  const maxLength = Math.max(str1.length, str2.length)
  if (maxLength === 0) return 100
  const distance = levenshteinDistance(str1.toLowerCase(), str2.toLowerCase())
  return ((maxLength - distance) / maxLength) * 100
}

/**
 * Autocorrect email domain typos.
 *
 * @param {string} email - Full email address
 * @param {number} threshold - Similarity threshold for fuzzy matching (default 75%)
 * @returns {{ corrected: string, original: string, wasCorrected: boolean }}
 */
export function autocorrectEmail(email, threshold = 75) {
  if (!email || !email.includes('@')) {
    return { corrected: email, original: '', wasCorrected: false }
  }

  const [localPart, domain] = email.split('@')
  if (!domain) return { corrected: email, original: '', wasCorrected: false }

  const domainLower = domain.toLowerCase()
  const parts = domainLower.split('.')

  const lastPart = parts[parts.length - 1]
  const isValidTLD = VALID_TLDS.includes(lastPart)
  const isCountryTLD = lastPart.length === 2 && isValidTLD

  const providerName = parts[0]
  const isKnownProvider = KNOWN_PROVIDERS.includes(providerName)

  const buildResult = (corrected) => ({
    corrected,
    original: corrected !== email ? email : '',
    wasCorrected: corrected !== email,
  })

  // CASE 1: Known provider + invalid TLD → correct only TLD
  if (isKnownProvider && !isValidTLD) {
    return buildResult(`${localPart}@${providerName}.com`.toLowerCase())
  }

  // CASE 2: Known provider + valid TLD → don't correct
  if (isKnownProvider && isValidTLD) {
    return buildResult(email)
  }

  // CASE 3: Check known typo map
  const knownTypo = KNOWN_TYPOS[providerName.toLowerCase()]
  if (knownTypo) {
    if (isCountryTLD) {
      return buildResult(`${localPart}@${knownTypo}.com.${lastPart}`.toLowerCase())
    }
    return buildResult(`${localPart}@${knownTypo}.com`.toLowerCase())
  }

  // CASE 4: Fuzzy match via Levenshtein distance
  let bestMatch = null
  let bestSimilarity = 0

  for (const provider of KNOWN_PROVIDERS) {
    const similarity = similarityPercentage(providerName, provider)
    if (similarity > bestSimilarity) {
      bestSimilarity = similarity
      bestMatch = provider
    }
  }

  if (bestMatch && bestSimilarity >= threshold) {
    if (isCountryTLD) {
      return buildResult(`${localPart}@${bestMatch}.com.${lastPart}`.toLowerCase())
    }
    return buildResult(`${localPart}@${bestMatch}.com`.toLowerCase())
  }

  return buildResult(email)
}
