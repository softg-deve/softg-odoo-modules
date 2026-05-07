/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class HexColorField extends Component {
    static template = "website_preheader_ticker.HexColorField";
    static props = { ...standardFieldProps };

    get currentValue() {
        const val = this.props.record.data[this.props.name];
        if (!val || typeof val !== "string" || !val.startsWith("#")) {
            return "#000000";
        }
        return val.length === 7 ? val : "#000000";
    }

    onColorChange(ev) {
        this.props.record.update({ [this.props.name]: ev.target.value });
    }
}

registry.category("fields").add("hex_color", {
    component: HexColorField,
    supportedTypes: ["char"],
});
