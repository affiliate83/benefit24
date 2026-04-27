<?php
/**
 * WP Code 스니펫 - PHP (Function snippet)
 * 메인 홈페이지 카드형 레이아웃 숏코드
 * 사용법: 정적 프론트 페이지의 본문에 [benefit24_home] 삽입
 */
function benefit24_homepage_content() {
    $args = [
        'post_type'      => 'post',
        'posts_per_page' => 12,
        'post_status'    => 'publish',
        'orderby'        => 'date',
        'order'          => 'DESC',
    ];
    $query = new WP_Query($args);

    ob_start();
    ?>

    <!-- 히어로 섹션 -->
    <div class="b24-hero">
        <div class="b24-hero-inner">
            <div class="b24-hero-badge">🔔 매일 업데이트</div>
            <h1 class="b24-hero-title">지원금알리미</h1>
            <p class="b24-hero-desc">
                복지·생활지원금 정보를 한곳에서<br>쉽고 빠르게 확인하세요
            </p>
            <div class="b24-hero-tags">
                <span>💰 생활비 지원</span>
                <span>🏠 주거 지원</span>
                <span>👴 노인 복지</span>
                <span>🏥 의료 지원</span>
                <span>📚 교육 지원</span>
            </div>
        </div>
    </div>

    <!-- 안내 배너 -->
    <div class="b24-notice">
        <span class="b24-notice-icon">📱</span>
        <span>앱 알림을 허용하시면 새 지원금 소식을 바로 받아보실 수 있습니다</span>
    </div>

    <!-- 포스트 카드 목록 -->
    <div class="b24-container">
        <div class="b24-section-header">
            <h2 class="b24-section-title">📋 최신 지원금 소식</h2>
        </div>

        <div class="b24-grid">
            <?php if ($query->have_posts()) : ?>
                <?php while ($query->have_posts()) : $query->the_post(); ?>
                    <?php
                        $cats     = get_the_category();
                        $cat_name = $cats ? esc_html($cats[0]->name) : '지원금';
                        $excerpt  = wp_trim_words(wp_strip_all_tags(get_the_excerpt()), 18, '…');
                    ?>
                    <a href="<?php the_permalink(); ?>" class="b24-card">
                        <div class="b24-card-thumb">
                            <?php if (has_post_thumbnail()) : ?>
                                <?php the_post_thumbnail('medium', ['loading' => 'lazy', 'alt' => get_the_title()]); ?>
                            <?php else : ?>
                                <div class="b24-card-thumb-default">💰</div>
                            <?php endif; ?>
                        </div>
                        <div class="b24-card-body">
                            <span class="b24-card-cat"><?php echo $cat_name; ?></span>
                            <h3 class="b24-card-title"><?php the_title(); ?></h3>
                            <?php if ($excerpt) : ?>
                                <p class="b24-card-excerpt"><?php echo esc_html($excerpt); ?></p>
                            <?php endif; ?>
                            <div class="b24-card-footer">
                                <span class="b24-card-date"><?php echo get_the_date('Y.m.d'); ?></span>
                                <span class="b24-card-more">자세히 보기 →</span>
                            </div>
                        </div>
                    </a>
                <?php endwhile; ?>
                <?php wp_reset_postdata(); ?>
            <?php else : ?>
                <p class="b24-empty">등록된 지원금 정보가 없습니다.</p>
            <?php endif; ?>
        </div>
    </div>

    <?php
    return ob_get_clean();
}
add_shortcode('benefit24_home', 'benefit24_homepage_content');