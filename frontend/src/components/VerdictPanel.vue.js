import { formatCurrency, formatRange } from '@/lib/format';
const __VLS_props = defineProps();
const severityColor = {
    high: 'negative',
    medium: 'warning',
    low: 'grey',
    info: 'info',
};
function yesNo(value) {
    if (value === null)
        return '—';
    return value ? 'yes' : 'no';
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
const __VLS_0 = {}.QCard;
/** @type {[typeof __VLS_components.QCard, typeof __VLS_components.qCard, typeof __VLS_components.QCard, typeof __VLS_components.qCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    flat: true,
    bordered: true,
    ...{ class: "q-mb-md" },
}));
const __VLS_2 = __VLS_1({
    flat: true,
    bordered: true,
    ...{ class: "q-mb-md" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_4 = {};
__VLS_3.slots.default;
const __VLS_5 = {}.QCardSection;
/** @type {[typeof __VLS_components.QCardSection, typeof __VLS_components.qCardSection, typeof __VLS_components.QCardSection, typeof __VLS_components.qCardSection, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(__VLS_5, new __VLS_5({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_8.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "row items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-h6" },
});
const __VLS_9 = {}.QChip;
/** @type {[typeof __VLS_components.QChip, typeof __VLS_components.qChip, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({
    label: (`Opportunity ${__VLS_ctx.verdict.opportunity_score.toFixed(0)}`),
    color: "primary",
    textColor: "white",
}));
const __VLS_11 = __VLS_10({
    label: (`Opportunity ${__VLS_ctx.verdict.opportunity_score.toFixed(0)}`),
    color: "primary",
    textColor: "white",
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-body2 text-grey-8 q-mt-sm" },
});
(__VLS_ctx.verdict.summary);
var __VLS_8;
const __VLS_13 = {}.QSeparator;
/** @type {[typeof __VLS_components.QSeparator, typeof __VLS_components.qSeparator, ]} */ ;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent(__VLS_13, new __VLS_13({}));
const __VLS_15 = __VLS_14({}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const __VLS_17 = {}.QCardSection;
/** @type {[typeof __VLS_components.QCardSection, typeof __VLS_components.qCardSection, typeof __VLS_components.QCardSection, typeof __VLS_components.qCardSection, ]} */ ;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
    ...{ class: "row q-col-gutter-md" },
}));
const __VLS_19 = __VLS_18({
    ...{ class: "row q-col-gutter-md" },
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
__VLS_20.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "col-12 col-sm-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-caption text-grey" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.yesNo(__VLS_ctx.verdict.can_build_by_right));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.verdict.by_right_units ?? '—');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.yesNo(__VLS_ctx.verdict.needs_variance));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "col-12 col-sm-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-caption text-grey" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.formatRange(__VLS_ctx.verdict.value_estimate_low, __VLS_ctx.verdict.value_estimate_high));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.formatCurrency(__VLS_ctx.verdict.assessment_market_gap));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "col-12 col-sm-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-caption text-grey" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.verdict.risk_score ?? '—');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "q-gutter-xs q-mt-xs" },
});
for (const [flag] of __VLS_getVForSourceType((__VLS_ctx.verdict.risk_flags))) {
    const __VLS_21 = {}.QChip;
    /** @type {[typeof __VLS_components.QChip, typeof __VLS_components.qChip, ]} */ ;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({
        key: (flag.code),
        dense: true,
        color: (__VLS_ctx.severityColor[flag.severity] ?? 'grey'),
        textColor: "white",
        label: (flag.label),
    }));
    const __VLS_23 = __VLS_22({
        key: (flag.code),
        dense: true,
        color: (__VLS_ctx.severityColor[flag.severity] ?? 'grey'),
        textColor: "white",
        label: (flag.label),
    }, ...__VLS_functionalComponentArgsRest(__VLS_22));
}
var __VLS_20;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['q-mb-md']} */ ;
/** @type {__VLS_StyleScopedClasses['row']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-h6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-body2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey-8']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mt-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['row']} */ ;
/** @type {__VLS_StyleScopedClasses['q-col-gutter-md']} */ ;
/** @type {__VLS_StyleScopedClasses['col-12']} */ ;
/** @type {__VLS_StyleScopedClasses['col-sm-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
/** @type {__VLS_StyleScopedClasses['col-12']} */ ;
/** @type {__VLS_StyleScopedClasses['col-sm-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
/** @type {__VLS_StyleScopedClasses['col-12']} */ ;
/** @type {__VLS_StyleScopedClasses['col-sm-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
/** @type {__VLS_StyleScopedClasses['q-gutter-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mt-xs']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            formatCurrency: formatCurrency,
            formatRange: formatRange,
            severityColor: severityColor,
            yesNo: yesNo,
        };
    },
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
