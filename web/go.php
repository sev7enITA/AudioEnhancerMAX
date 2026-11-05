<?php
declare(strict_types=1);

// Count aggregate navigation requests only. No cookie, visitor ID, IP,
// referrer, user-agent, submitted text or full query string is persisted.
header('Cache-Control: no-store, private');
header('Referrer-Policy: no-referrer');
header('X-Robots-Tag: noindex, nofollow');
header('Vary: DNT, Sec-GPC');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
if (!in_array($method, ['GET', 'HEAD'], true)) {
    http_response_code(405);
    header('Allow: GET, HEAD');
    exit;
}
$targets = [
    'app-store' => 'https://apps.apple.com/app/audioenhancermax/id6791591803',
    'dmg' => 'https://github.com/sev7enITA/AudioEnhancerMAX/releases/download/v3.9.0/AudioEnhancerMAX-v3.9.0-build-3.9.2-macOS-arm64.dmg',
    'download' => 'https://www.fabriziodegni.com/AudioEnhancerMAX/download.html',
    'feedback' => 'https://www.fabriziodegni.com/AudioEnhancerMAX/feedback.html',
];
function field(string $name, array $allowed, string $fallback): string {
    $value = $_GET[$name] ?? null;
    return is_string($value) && in_array($value, $allowed, true) ? $value : $fallback;
}
$target = field('to', array_keys($targets), '');
if ($target === '') {
    http_response_code(400);
    header('Content-Type: text/plain; charset=utf-8');
    echo "Choose a valid AudioEnhancerMAX destination.\n";
    exit;
}
$source = field('source', ['website','linkedin','x','facebook','instagram','reddit','sourceforge','gearspace','kvr','product-hunt','youtube','bilibili','appinn','newsletter','qa','unknown'], 'unknown');
$campaign = field('campaign', ['launch-2026-11','field-test-2026-11','verification-2026-11'], 'launch-2026-11');
$placement = field('placement', ['hero','download-card','download-page','feedback-page','profile','post','testers','resource','other'], 'other');
$location = $targets[$target];
if (in_array($target, ['download','feedback'], true)) {
    $location .= '?' . http_build_query(['utm_source'=>$source,'utm_medium'=>'community','utm_campaign'=>$campaign,'utm_content'=>$placement], '', '&', PHP_QUERY_RFC3986);
}
$measurement = 'not-recorded';
$agent = $_SERVER['HTTP_USER_AGENT'] ?? '';
$purpose = ($_SERVER['HTTP_SEC_PURPOSE'] ?? '') . ' ' . ($_SERVER['HTTP_PURPOSE'] ?? '');
if ($method === 'HEAD' || ($_GET['test'] ?? '') === '1') {
    $measurement = 'test';
} elseif (($_SERVER['HTTP_DNT'] ?? '') === '1' || ($_SERVER['HTTP_SEC_GPC'] ?? '') === '1') {
    $measurement = 'opt-out';
} elseif (preg_match('/bot|crawler|spider|preview|facebookexternalhit|slackbot|discordbot/i', $agent) || stripos($purpose, 'prefetch') !== false) {
    $measurement = 'automated';
} else {
    $lock = false;
    $temporary = null;
    try {
        // On the production host, this is outside public_html.
        $directory = getenv('AEMAX_METRICS_DIR') ?: dirname(__DIR__, 2) . '/.aemax-metrics';
        if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
            throw new RuntimeException('Private storage unavailable');
        }
        $resolved = realpath($directory);
        $documentRoot = realpath($_SERVER['DOCUMENT_ROOT'] ?? __DIR__);
        if ($resolved === false || ($documentRoot !== false && ($resolved === $documentRoot || str_starts_with($resolved, $documentRoot . '/')))) {
            throw new RuntimeException('Storage must be outside the public document root');
        }
        $lock = @fopen($resolved . '/counts.lock', 'c');
        if ($lock === false || !flock($lock, LOCK_EX)) {
            throw new RuntimeException('Could not lock counters');
        }
        @chmod($resolved . '/counts.lock', 0600);
        $file = $resolved . '/counts.json';
        $data = ['schema_version'=>1,'metric'=>'navigation_requests','timezone'=>'UTC','days'=>[]];
        if (is_file($file)) {
            $raw = file_get_contents($file);
            $data = json_decode($raw === false ? '' : $raw, true, 512, JSON_THROW_ON_ERROR);
            if (!is_array($data['days'] ?? null)) {
                throw new RuntimeException('Invalid counters');
            }
        }
        $cutoff = gmdate('Y-m-d', time() - 89 * 86400);
        foreach (array_keys($data['days']) as $day) {
            if ($day < $cutoff) unset($data['days'][$day]);
        }
        $today = gmdate('Y-m-d');
        $key = implode('|', [$source,$campaign,$target,$placement]);
        $data['days'][$today][$key] = (int)($data['days'][$today][$key] ?? 0) + 1;
        $encoded = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR) . "\n";
        $temporary = tempnam($resolved, '.count-');
        if ($temporary === false || file_put_contents($temporary, $encoded) !== strlen($encoded) || !rename($temporary, $file)) {
            throw new RuntimeException('Could not save counters');
        }
        @chmod($file, 0600);
        $temporary = null;
        $measurement = 'recorded';
    } catch (Throwable $error) {
        // Navigation remains available if measurement storage fails.
        $measurement = 'unavailable';
    } finally {
        if (is_string($temporary) && is_file($temporary)) @unlink($temporary);
        if (is_resource($lock)) {
            flock($lock, LOCK_UN);
            fclose($lock);
        }
    }
}
header('X-AEMAX-Measurement: ' . $measurement);
header('Location: ' . $location, true, 302);
exit;
