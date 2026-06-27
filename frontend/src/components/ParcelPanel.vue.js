import { storeToRefs } from 'pinia';
import AskBox from '@/components/AskBox.vue';
import VerdictPanel from '@/components/VerdictPanel.vue';
import { formatCurrency } from '@/lib/format';
import { useParcelStore } from '@/stores/parcel';
const store = useParcelStore();
const { detail, verdict, loading, error } = storeToRefs(store);
function yesNo(value) {
    if (value === null)
        return '—';
    return value ? 'yes' : 'no';
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "q-pa-md relative-position" },
});
const __VLS_0 = {}.QInnerLoading;
/** @type {[typeof __VLS_components.QInnerLoading, typeof __VLS_components.qInnerLoading, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    showing: (__VLS_ctx.loading),
}));
const __VLS_2 = __VLS_1({
    showing: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
if (__VLS_ctx.error) {
    const __VLS_4 = {}.QBanner;
    /** @type {[typeof __VLS_components.QBanner, typeof __VLS_components.qBanner, typeof __VLS_components.QBanner, typeof __VLS_components.qBanner, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        ...{ class: "bg-red-1 text-negative" },
    }));
    const __VLS_6 = __VLS_5({
        ...{ class: "bg-red-1 text-negative" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_7.slots.default;
    (__VLS_ctx.error);
    var __VLS_7;
}
if (__VLS_ctx.detail) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-h6" },
    });
    (__VLS_ctx.detail.address ?? __VLS_ctx.detail.parcel_number);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-caption text-grey" },
    });
    (__VLS_ctx.detail.parcel_number);
    (__VLS_ctx.detail.base_zoning_code ?? 'zoning unknown');
    const __VLS_8 = {}.QList;
    /** @type {[typeof __VLS_components.QList, typeof __VLS_components.qList, typeof __VLS_components.QList, typeof __VLS_components.qList, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        dense: true,
        ...{ class: "q-my-md" },
    }));
    const __VLS_10 = __VLS_9({
        dense: true,
        ...{ class: "q-my-md" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    const __VLS_12 = {}.QItem;
    /** @type {[typeof __VLS_components.QItem, typeof __VLS_components.qItem, typeof __VLS_components.QItem, typeof __VLS_components.qItem, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    const __VLS_16 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
    const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    var __VLS_19;
    const __VLS_20 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        side: true,
    }));
    const __VLS_22 = __VLS_21({
        side: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    (__VLS_ctx.detail.owner ?? '—');
    var __VLS_23;
    var __VLS_15;
    const __VLS_24 = {}.QItem;
    /** @type {[typeof __VLS_components.QItem, typeof __VLS_components.qItem, typeof __VLS_components.QItem, typeof __VLS_components.qItem, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
    const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    const __VLS_28 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
    const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    var __VLS_31;
    const __VLS_32 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        side: true,
    }));
    const __VLS_34 = __VLS_33({
        side: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    (__VLS_ctx.detail.lot_area_sqft ?? '—');
    var __VLS_35;
    var __VLS_27;
    const __VLS_36 = {}.QItem;
    /** @type {[typeof __VLS_components.QItem, typeof __VLS_components.qItem, typeof __VLS_components.QItem, typeof __VLS_components.qItem, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({}));
    const __VLS_38 = __VLS_37({}, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    const __VLS_40 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
    const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    var __VLS_43;
    const __VLS_44 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        side: true,
    }));
    const __VLS_46 = __VLS_45({
        side: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    (__VLS_ctx.formatCurrency(__VLS_ctx.detail.market_value));
    var __VLS_47;
    var __VLS_39;
    const __VLS_48 = {}.QItem;
    /** @type {[typeof __VLS_components.QItem, typeof __VLS_components.qItem, typeof __VLS_components.QItem, typeof __VLS_components.qItem, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
    const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    const __VLS_52 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
    const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    var __VLS_55;
    const __VLS_56 = {}.QItemSection;
    /** @type {[typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, typeof __VLS_components.QItemSection, typeof __VLS_components.qItemSection, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        side: true,
    }));
    const __VLS_58 = __VLS_57({
        side: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    (__VLS_ctx.yesNo(__VLS_ctx.detail.is_vacant));
    var __VLS_59;
    var __VLS_51;
    var __VLS_11;
    const __VLS_60 = {}.QBtn;
    /** @type {[typeof __VLS_components.QBtn, typeof __VLS_components.qBtn, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        ...{ 'onClick': {} },
        dense: true,
        color: "primary",
        label: "Refresh verdict",
        ...{ class: "q-mb-md" },
    }));
    const __VLS_62 = __VLS_61({
        ...{ 'onClick': {} },
        dense: true,
        color: "primary",
        label: "Refresh verdict",
        ...{ class: "q-mb-md" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    let __VLS_64;
    let __VLS_65;
    let __VLS_66;
    const __VLS_67 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.detail))
                return;
            __VLS_ctx.store.refreshVerdict();
        }
    };
    var __VLS_63;
    if (__VLS_ctx.verdict) {
        /** @type {[typeof VerdictPanel, ]} */ ;
        // @ts-ignore
        const __VLS_68 = __VLS_asFunctionalComponent(VerdictPanel, new VerdictPanel({
            verdict: (__VLS_ctx.verdict),
        }));
        const __VLS_69 = __VLS_68({
            verdict: (__VLS_ctx.verdict),
        }, ...__VLS_functionalComponentArgsRest(__VLS_68));
    }
    else {
        const __VLS_71 = {}.QBanner;
        /** @type {[typeof __VLS_components.QBanner, typeof __VLS_components.qBanner, typeof __VLS_components.QBanner, typeof __VLS_components.qBanner, ]} */ ;
        // @ts-ignore
        const __VLS_72 = __VLS_asFunctionalComponent(__VLS_71, new __VLS_71({
            dense: true,
            ...{ class: "bg-grey-2 q-mb-md" },
        }));
        const __VLS_73 = __VLS_72({
            dense: true,
            ...{ class: "bg-grey-2 q-mb-md" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_72));
        __VLS_74.slots.default;
        var __VLS_74;
    }
    /** @type {[typeof AskBox, ]} */ ;
    // @ts-ignore
    const __VLS_75 = __VLS_asFunctionalComponent(AskBox, new AskBox({
        parcelNumber: (__VLS_ctx.detail.parcel_number),
    }));
    const __VLS_76 = __VLS_75({
        parcelNumber: (__VLS_ctx.detail.parcel_number),
    }, ...__VLS_functionalComponentArgsRest(__VLS_75));
}
else if (!__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-grey text-center q-pa-xl" },
    });
}
/** @type {__VLS_StyleScopedClasses['q-pa-md']} */ ;
/** @type {__VLS_StyleScopedClasses['relative-position']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-negative']} */ ;
/** @type {__VLS_StyleScopedClasses['text-h6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-caption']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
/** @type {__VLS_StyleScopedClasses['q-my-md']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mb-md']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-grey-2']} */ ;
/** @type {__VLS_StyleScopedClasses['q-mb-md']} */ ;
/** @type {__VLS_StyleScopedClasses['text-grey']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['q-pa-xl']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AskBox: AskBox,
            VerdictPanel: VerdictPanel,
            formatCurrency: formatCurrency,
            store: store,
            detail: detail,
            verdict: verdict,
            loading: loading,
            error: error,
            yesNo: yesNo,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
