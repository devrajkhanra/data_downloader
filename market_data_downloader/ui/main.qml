import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1360
    height: 900
    minimumWidth: 1060
    minimumHeight: 780
    visible: true
    title: "Market Data Studio"
    color: backgroundColor

    property bool darkMode: true
    property string initialStartDate: ""
    property string endDate: Qt.formatDate(new Date(), "yyyy-MM-dd")
    readonly property color backgroundColor: darkMode ? "#10151d" : "#eef1f5"
    readonly property color surfaceColor: darkMode ? "#171e28" : "#ffffff"
    readonly property color raisedColor: darkMode ? "#202936" : "#f7f9fc"
    readonly property color fieldColor: darkMode ? "#111821" : "#ffffff"
    readonly property color textColor: darkMode ? "#edf2f7" : "#17212f"
    readonly property color mutedColor: darkMode ? "#9aa7b7" : "#647184"
    readonly property color borderColor: darkMode ? "#303b49" : "#d3dbe5"
    readonly property color accentColor: darkMode ? "#64a5ff" : "#1769d2"
    readonly property color accentSoftColor: darkMode ? "#1c3551" : "#e5f0ff"
    readonly property color successColor: darkMode ? "#67d6a0" : "#16804a"
    readonly property color warningColor: darkMode ? "#f2c66d" : "#a86900"
    readonly property color errorColor: darkMode ? "#ff8e8e" : "#ba3038"

    function countSelected(items) {
        let count = 0
        for (let i = 0; i < items.length; i++) {
            if (controller.selectedKeys.includes(items[i].key))
                count++
        }
        return count
    }

    function setAll(items, selected) {
        for (let i = 0; i < items.length; i++)
            controller.setSelected(items[i].key, selected)
    }

    component SurfacePanel: Rectangle {
        color: window.surfaceColor
        radius: 3
        border.color: window.borderColor
        border.width: 1
        Behavior on color { ColorAnimation { duration: 160 } }
        Behavior on border.color { ColorAnimation { duration: 160 } }
    }

    component Eyebrow: Label {
        color: window.mutedColor
        font.pixelSize: 10
        font.weight: Font.DemiBold
        font.letterSpacing: 0.9
    }

    component FlatButton: Button {
        id: flatButton
        property bool primary: false
        implicitHeight: 36
        padding: 10
        font.pixelSize: 12
        font.weight: Font.DemiBold
        contentItem: Text {
            text: flatButton.text
            color: !flatButton.enabled ? window.mutedColor
                : flatButton.primary ? "#ffffff" : window.textColor
            font: flatButton.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 2
            color: !flatButton.enabled ? window.raisedColor
                : flatButton.primary
                    ? flatButton.down ? Qt.darker(window.accentColor, 1.2) : window.accentColor
                    : flatButton.hovered ? window.raisedColor : "transparent"
            border.color: flatButton.primary ? window.accentColor : window.borderColor
            Behavior on color { ColorAnimation { duration: 120 } }
        }
    }

    component Glyph: Item {
        id: glyph
        property string name: ""
        property color tint: window.mutedColor
        implicitWidth: 18
        implicitHeight: 18

        Canvas {
            id: drawing
            anchors.fill: parent

            onPaint: {
                const ctx = getContext("2d")
                ctx.clearRect(0, 0, width, height)
                ctx.strokeStyle = glyph.tint
                ctx.fillStyle = glyph.tint
                ctx.lineWidth = 1.7
                ctx.lineCap = "round"
                ctx.lineJoin = "round"
                ctx.beginPath()

                switch (glyph.name) {
                case "market":
                case "broad":
                    ctx.moveTo(3, 15)
                    ctx.lineTo(3, 3)
                    ctx.moveTo(3, 15)
                    ctx.lineTo(16, 15)
                    ctx.moveTo(6, 12)
                    ctx.lineTo(6, 9)
                    ctx.moveTo(10, 12)
                    ctx.lineTo(10, 6)
                    ctx.moveTo(14, 12)
                    ctx.lineTo(14, 3)
                    ctx.stroke()
                    break
                case "sector":
                    ctx.moveTo(9, 2)
                    ctx.arc(9, 9, 7, -Math.PI / 2, Math.PI * 1.5)
                    ctx.moveTo(9, 9)
                    ctx.lineTo(9, 2)
                    ctx.moveTo(9, 9)
                    ctx.lineTo(16, 9)
                    ctx.stroke()
                    break
                case "stock":
                    ctx.moveTo(2, 15)
                    ctx.lineTo(2, 3)
                    ctx.moveTo(2, 15)
                    ctx.lineTo(16, 15)
                    ctx.moveTo(4, 12)
                    ctx.lineTo(7, 9)
                    ctx.lineTo(10, 11)
                    ctx.lineTo(15, 5)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(12, 5)
                    ctx.lineTo(15, 5)
                    ctx.lineTo(15, 8)
                    ctx.stroke()
                    break
                case "options":
                    ctx.moveTo(3, 3)
                    ctx.lineTo(3, 15)
                    ctx.moveTo(9, 3)
                    ctx.lineTo(9, 15)
                    ctx.moveTo(15, 3)
                    ctx.lineTo(15, 15)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.arc(3, 7, 2, 0, Math.PI * 2)
                    ctx.arc(9, 12, 2, 0, Math.PI * 2)
                    ctx.arc(15, 5, 2, 0, Math.PI * 2)
                    ctx.fill()
                    break
                case "calendar":
                    ctx.rect(2, 4, 14, 12)
                    ctx.moveTo(2, 7)
                    ctx.lineTo(16, 7)
                    ctx.moveTo(6, 2)
                    ctx.lineTo(6, 5)
                    ctx.moveTo(12, 2)
                    ctx.lineTo(12, 5)
                    ctx.stroke()
                    break
                case "download":
                    ctx.moveTo(9, 2)
                    ctx.lineTo(9, 11)
                    ctx.moveTo(5, 8)
                    ctx.lineTo(9, 12)
                    ctx.lineTo(13, 8)
                    ctx.moveTo(3, 14)
                    ctx.lineTo(15, 14)
                    ctx.stroke()
                    break
                case "sun":
                    ctx.arc(9, 9, 3.2, 0, Math.PI * 2)
                    ctx.moveTo(9, 1)
                    ctx.lineTo(9, 3)
                    ctx.moveTo(9, 15)
                    ctx.lineTo(9, 17)
                    ctx.moveTo(1, 9)
                    ctx.lineTo(3, 9)
                    ctx.moveTo(15, 9)
                    ctx.lineTo(17, 9)
                    ctx.moveTo(3.3, 3.3)
                    ctx.lineTo(4.7, 4.7)
                    ctx.moveTo(13.3, 13.3)
                    ctx.lineTo(14.7, 14.7)
                    ctx.moveTo(14.7, 3.3)
                    ctx.lineTo(13.3, 4.7)
                    ctx.moveTo(4.7, 13.3)
                    ctx.lineTo(3.3, 14.7)
                    ctx.stroke()
                    break
                case "moon":
                    ctx.arc(9, 9, 6, -Math.PI * 0.35, Math.PI * 0.9)
                    ctx.arc(12, 6, 5, Math.PI * 0.7, -Math.PI * 0.4, true)
                    ctx.stroke()
                    break
                case "chevron-left":
                    ctx.moveTo(11, 3)
                    ctx.lineTo(5, 9)
                    ctx.lineTo(11, 15)
                    ctx.stroke()
                    break
                case "chevron-right":
                    ctx.moveTo(7, 3)
                    ctx.lineTo(13, 9)
                    ctx.lineTo(7, 15)
                    ctx.stroke()
                    break
                case "refresh":
                    ctx.arc(9, 9, 6, -Math.PI * 0.7, Math.PI * 0.8)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(3, 3)
                    ctx.lineTo(3, 7)
                    ctx.lineTo(7, 7)
                    ctx.stroke()
                    break
                case "play":
                    ctx.moveTo(6, 3)
                    ctx.lineTo(15, 9)
                    ctx.lineTo(6, 15)
                    ctx.closePath()
                    ctx.fill()
                    break
                }
            }
        }

        onNameChanged: drawing.requestPaint()
        onTintChanged: drawing.requestPaint()
        Component.onCompleted: drawing.requestPaint()
    }

    component DatePickerField: Item {
        id: dateField
        property string label
        property string dateValue
        property bool optional: false
        property bool fieldEnabled: true
        signal dateSelected(string value)
        implicitHeight: 66

        ColumnLayout {
            anchors.fill: parent
            spacing: 5

            Label {
                text: dateField.label
                color: window.mutedColor
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 0.5
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 4

                Button {
                    id: dateButton
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    enabled: dateField.fieldEnabled
                    onClicked: calendarPopup.openForDate()

                    contentItem: RowLayout {
                        spacing: 8
                        Glyph {
                            name: "calendar"
                            tint: dateField.dateValue ? window.accentColor : window.mutedColor
                        }
                        Label {
                            Layout.fillWidth: true
                            text: dateField.dateValue || (dateField.optional
                                ? "Not set"
                                : "Choose end date")
                            color: dateField.dateValue ? window.textColor : window.mutedColor
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                    background: Rectangle {
                        color: dateButton.hovered ? window.raisedColor : window.fieldColor
                        border.color: dateButton.activeFocus ? window.accentColor : window.borderColor
                        border.width: 1
                        radius: 2
                        Behavior on color { ColorAnimation { duration: 120 } }
                    }
                }

                Button {
                    visible: dateField.optional && dateField.dateValue.length > 0
                    Layout.preferredWidth: 32
                    Layout.preferredHeight: 36
                    text: "×"
                    enabled: dateField.fieldEnabled
                    onClicked: dateField.dateSelected("")
                    contentItem: Text {
                        text: parent.text
                        color: window.mutedColor
                        font.pixelSize: 17
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: parent.hovered ? window.raisedColor : "transparent"
                        border.color: window.borderColor
                        radius: 2
                    }
                }
            }
        }

        Popup {
            id: calendarPopup
            parent: Overlay.overlay
            width: 296
            height: 344
            padding: 12
            modal: false
            focus: true
            closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

            property int shownYear: new Date().getFullYear()
            property int shownMonth: new Date().getMonth()

            function openForDate() {
                const source = dateField.dateValue
                    ? new Date(dateField.dateValue + "T00:00:00")
                    : new Date()
                shownYear = source.getFullYear()
                shownMonth = source.getMonth()
                const position = dateField.mapToItem(
                    calendarPopup.parent, 0, dateField.height + 5
                )
                calendarPopup.x = Math.max(
                    8, Math.min(position.x, calendarPopup.parent.width - calendarPopup.width - 8)
                )
                calendarPopup.y = Math.max(
                    8, Math.min(position.y, calendarPopup.parent.height - calendarPopup.height - 8)
                )
                open()
            }

            enter: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 110 }
                NumberAnimation { property: "scale"; from: 0.98; to: 1; duration: 110 }
            }
            exit: Transition {
                NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 80 }
            }

            background: Rectangle {
                color: window.surfaceColor
                border.color: window.borderColor
                radius: 3
            }

            contentItem: ColumnLayout {
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
                        onClicked: {
                            if (calendarPopup.shownMonth === 0) {
                                calendarPopup.shownMonth = 11
                                calendarPopup.shownYear--
                            } else {
                                calendarPopup.shownMonth--
                            }
                        }
                        contentItem: Glyph { name: "chevron-left"; tint: window.textColor }
                        background: Rectangle {
                            color: parent.hovered ? window.raisedColor : "transparent"
                            radius: 2
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: Qt.formatDate(
                            new Date(calendarPopup.shownYear, calendarPopup.shownMonth, 1),
                            "MMMM yyyy"
                        )
                        color: window.textColor
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Button {
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
                        onClicked: {
                            if (calendarPopup.shownMonth === 11) {
                                calendarPopup.shownMonth = 0
                                calendarPopup.shownYear++
                            } else {
                                calendarPopup.shownMonth++
                            }
                        }
                        contentItem: Glyph { name: "chevron-right"; tint: window.textColor }
                        background: Rectangle {
                            color: parent.hovered ? window.raisedColor : "transparent"
                            radius: 2
                        }
                    }
                }

                MonthGrid {
                    id: calendarGrid
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    month: calendarPopup.shownMonth
                    year: calendarPopup.shownYear
                    palette.window: window.surfaceColor
                    palette.button: window.surfaceColor
                    palette.text: window.textColor
                    palette.buttonText: window.textColor
                    palette.highlight: window.accentColor
                    palette.highlightedText: "#ffffff"
                    onClicked: function(selectedDate) {
                        dateField.dateSelected(Qt.formatDate(selectedDate, "yyyy-MM-dd"))
                        calendarPopup.close()
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: "Today"
                        flat: true
                        onClicked: {
                            dateField.dateSelected(Qt.formatDate(new Date(), "yyyy-MM-dd"))
                            calendarPopup.close()
                        }
                        contentItem: Text {
                            text: parent.text
                            color: window.accentColor
                            font.pixelSize: 11
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        visible: dateField.optional
                        text: "Clear"
                        flat: true
                        onClicked: {
                            dateField.dateSelected("")
                            calendarPopup.close()
                        }
                        contentItem: Text {
                            text: parent.text
                            color: window.mutedColor
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }
    }

    header: Rectangle {
        height: 58
        color: surfaceColor
        border.color: borderColor
        border.width: 1
        Behavior on color { ColorAnimation { duration: 160 } }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            spacing: 12

            Glyph {
                name: "market"
                tint: accentColor
                implicitWidth: 22
                implicitHeight: 22
            }
            Label {
                text: "Market Data Studio"
                color: textColor
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Rectangle {
                Layout.preferredWidth: 1
                Layout.preferredHeight: 22
                color: borderColor
            }
            Label {
                text: "NSE · Historical data"
                color: mutedColor
                font.pixelSize: 11
            }
            Item { Layout.fillWidth: true }

            Rectangle {
                Layout.preferredWidth: 8
                Layout.preferredHeight: 8
                radius: 4
                color: controller.busy ? warningColor : successColor
            }
            Label {
                text: controller.busy ? "WORKING" : "READY"
                color: mutedColor
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 0.5
            }
            Button {
                Layout.preferredWidth: 112
                Layout.preferredHeight: 34
                onClicked: window.darkMode = !window.darkMode
                contentItem: RowLayout {
                    spacing: 7
                    Glyph {
                        name: window.darkMode ? "sun" : "moon"
                        tint: window.textColor
                    }
                    Label {
                        text: window.darkMode ? "Light theme" : "Dark theme"
                        color: window.textColor
                        font.pixelSize: 10
                    }
                }
                background: Rectangle {
                    color: parent.hovered ? raisedColor : "transparent"
                    border.color: borderColor
                    radius: 2
                    Behavior on color { ColorAnimation { duration: 120 } }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            ColumnLayout {
                spacing: 2
                Label {
                    text: "Historical downloads"
                    color: textColor
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                }
                Label {
                    text: "Choose a market, configure the date range, and run a resumable job."
                    color: mutedColor
                    font.pixelSize: 11
                }
            }
            Item { Layout.fillWidth: true }
            Label {
                text: controller.selectedCount + " selected"
                color: accentColor
                font.pixelSize: 11
                font.weight: Font.DemiBold
                padding: 7
                background: Rectangle {
                    color: accentSoftColor
                    radius: 2
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 430
            spacing: 12

            SurfacePanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 540
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    TabBar {
                        id: dataTabs
                        Layout.fillWidth: true
                        Layout.preferredHeight: 44

                        background: Rectangle { color: "transparent" }

                        TabButton {
                            id: broadTab
                            text: "Broad"
                            contentItem: RowLayout {
                                spacing: 7
                                Glyph {
                                    name: "broad"
                                    tint: broadTab.checked ? window.accentColor : window.mutedColor
                                }
                                Label {
                                    text: broadTab.text
                                    color: broadTab.checked ? window.textColor : window.mutedColor
                                    font.pixelSize: 11
                                    font.weight: broadTab.checked ? Font.DemiBold : Font.Normal
                                }
                                Label {
                                    text: window.countSelected(controller.broadChoices)
                                    color: broadTab.checked ? window.accentColor : window.mutedColor
                                    font.pixelSize: 10
                                }
                            }
                            background: Rectangle {
                                color: broadTab.checked ? window.accentSoftColor : "transparent"
                                border.color: broadTab.checked ? window.accentColor : window.borderColor
                                radius: 2
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }
                        TabButton {
                            id: sectorTab
                            text: "Sector"
                            contentItem: RowLayout {
                                spacing: 7
                                Glyph {
                                    name: "sector"
                                    tint: sectorTab.checked ? window.accentColor : window.mutedColor
                                }
                                Label {
                                    text: sectorTab.text
                                    color: sectorTab.checked ? window.textColor : window.mutedColor
                                    font.pixelSize: 11
                                    font.weight: sectorTab.checked ? Font.DemiBold : Font.Normal
                                }
                                Label {
                                    text: window.countSelected(controller.sectorChoices)
                                    color: sectorTab.checked ? window.accentColor : window.mutedColor
                                    font.pixelSize: 10
                                }
                            }
                            background: Rectangle {
                                color: sectorTab.checked ? window.accentSoftColor : "transparent"
                                border.color: sectorTab.checked ? window.accentColor : window.borderColor
                                radius: 2
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }
                        TabButton {
                            id: stockTab
                            text: "Stocks"
                            contentItem: RowLayout {
                                spacing: 7
                                Glyph {
                                    name: "stock"
                                    tint: stockTab.checked ? window.accentColor : window.mutedColor
                                }
                                Label {
                                    text: stockTab.text
                                    color: stockTab.checked ? window.textColor : window.mutedColor
                                    font.pixelSize: 11
                                    font.weight: stockTab.checked ? Font.DemiBold : Font.Normal
                                }
                                Label {
                                    text: controller.selectedKeys.includes("stocks") ? "1" : "0"
                                    color: stockTab.checked ? window.accentColor : window.mutedColor
                                    font.pixelSize: 10
                                }
                            }
                            background: Rectangle {
                                color: stockTab.checked ? window.accentSoftColor : "transparent"
                                border.color: stockTab.checked ? window.accentColor : window.borderColor
                                radius: 2
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }
                        TabButton {
                            id: optionsTab
                            text: "Options"
                            contentItem: RowLayout {
                                spacing: 7
                                Glyph {
                                    name: "options"
                                    tint: optionsTab.checked ? window.accentColor : window.mutedColor
                                }
                                Label {
                                    text: optionsTab.text
                                    color: optionsTab.checked ? window.textColor : window.mutedColor
                                    font.pixelSize: 11
                                    font.weight: optionsTab.checked ? Font.DemiBold : Font.Normal
                                }
                                Label {
                                    text: controller.selectedKeys.includes("options") ? "1" : "0"
                                    color: optionsTab.checked ? window.accentColor : window.mutedColor
                                    font.pixelSize: 10
                                }
                            }
                            background: Rectangle {
                                color: optionsTab.checked ? window.accentSoftColor : "transparent"
                                border.color: optionsTab.checked ? window.accentColor : window.borderColor
                                radius: 2
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }
                        }
                    }

                    StackLayout {
                        id: dataPages
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        currentIndex: dataTabs.currentIndex
                        opacity: 1

                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 10
                                RowLayout {
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        spacing: 2
                                        Label {
                                            text: "Broad-market indices"
                                            color: window.textColor
                                            font.pixelSize: 14
                                            font.weight: Font.DemiBold
                                        }
                                        Label {
                                            text: controller.broadChoices.length + " available"
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Button {
                                        text: "Select all"
                                        flat: true
                                        enabled: !controller.busy
                                        onClicked: window.setAll(controller.broadChoices, true)
                                        contentItem: Text {
                                            text: parent.text
                                            color: window.accentColor
                                            font.pixelSize: 10
                                        }
                                    }
                                    Button {
                                        text: "Clear"
                                        flat: true
                                        enabled: !controller.busy
                                        onClicked: window.setAll(controller.broadChoices, false)
                                        contentItem: Text {
                                            text: parent.text
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                        }
                                    }
                                }

                                GridView {
                                    id: broadGrid
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    cellWidth: Math.max(220, width / 2)
                                    cellHeight: 42
                                    clip: true
                                    model: controller.broadChoices
                                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: broadGrid.cellWidth - 8
                                        height: 36
                                        property bool checked: controller.selectedKeys.includes(modelData.key)
                                        color: checked ? window.accentSoftColor
                                            : tileMouse.containsMouse ? window.raisedColor : "transparent"
                                        border.color: checked ? window.accentColor : window.borderColor
                                        radius: 2
                                        Behavior on color { ColorAnimation { duration: 110 } }
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 9
                                            anchors.rightMargin: 9
                                            spacing: 8
                                            Rectangle {
                                                Layout.preferredWidth: 15
                                                Layout.preferredHeight: 15
                                                color: parent.parent.checked ? window.accentColor : "transparent"
                                                border.color: parent.parent.checked ? window.accentColor : window.borderColor
                                                radius: 1
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✓"
                                                    visible: parent.parent.parent.checked
                                                    color: "#ffffff"
                                                    font.pixelSize: 10
                                                }
                                            }
                                            Label {
                                                Layout.fillWidth: true
                                                text: modelData.name
                                                color: window.textColor
                                                font.pixelSize: 11
                                                elide: Text.ElideRight
                                            }
                                        }
                                        MouseArea {
                                            id: tileMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            enabled: !controller.busy
                                            onClicked: controller.setSelected(
                                                modelData.key,
                                                !parent.checked
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 10
                                RowLayout {
                                    Layout.fillWidth: true
                                    ColumnLayout {
                                        spacing: 2
                                        Label {
                                            text: "Sector indices"
                                            color: window.textColor
                                            font.pixelSize: 14
                                            font.weight: Font.DemiBold
                                        }
                                        Label {
                                            text: controller.sectorChoices.length + " available"
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Button {
                                        text: "Select all"
                                        flat: true
                                        enabled: !controller.busy
                                        onClicked: window.setAll(controller.sectorChoices, true)
                                        contentItem: Text {
                                            text: parent.text
                                            color: window.accentColor
                                            font.pixelSize: 10
                                        }
                                    }
                                    Button {
                                        text: "Clear"
                                        flat: true
                                        enabled: !controller.busy
                                        onClicked: window.setAll(controller.sectorChoices, false)
                                        contentItem: Text {
                                            text: parent.text
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                        }
                                    }
                                }

                                GridView {
                                    id: sectorGrid
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    cellWidth: Math.max(220, width / 2)
                                    cellHeight: 42
                                    clip: true
                                    model: controller.sectorChoices
                                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: sectorGrid.cellWidth - 8
                                        height: 36
                                        property bool checked: controller.selectedKeys.includes(modelData.key)
                                        color: checked ? window.accentSoftColor
                                            : tileMouse.containsMouse ? window.raisedColor : "transparent"
                                        border.color: checked ? window.accentColor : window.borderColor
                                        radius: 2
                                        Behavior on color { ColorAnimation { duration: 110 } }
                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: 9
                                            anchors.rightMargin: 9
                                            spacing: 8
                                            Rectangle {
                                                Layout.preferredWidth: 15
                                                Layout.preferredHeight: 15
                                                color: parent.parent.checked ? window.accentColor : "transparent"
                                                border.color: parent.parent.checked ? window.accentColor : window.borderColor
                                                radius: 1
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✓"
                                                    visible: parent.parent.parent.checked
                                                    color: "#ffffff"
                                                    font.pixelSize: 10
                                                }
                                            }
                                            Label {
                                                Layout.fillWidth: true
                                                text: modelData.name
                                                color: window.textColor
                                                font.pixelSize: 11
                                                elide: Text.ElideRight
                                            }
                                        }
                                        MouseArea {
                                            id: tileMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            enabled: !controller.busy
                                            onClicked: controller.setSelected(
                                                modelData.key,
                                                !parent.checked
                                            )
                                        }
                                    }
                                }
                            }
                        }

                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 12
                                Label {
                                    text: "NSE cash equities"
                                    color: window.textColor
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Label {
                                    text: "Refresh the official NSE list and include active SERIES=EQ instruments matched to Upstox."
                                    color: window.mutedColor
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 92
                                    property bool checked: controller.selectedKeys.includes("stocks")
                                    color: checked ? window.accentSoftColor : window.raisedColor
                                    border.color: checked ? window.accentColor : window.borderColor
                                    radius: 2
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 12
                                        Glyph {
                                            name: "stock"
                                            tint: window.accentColor
                                            implicitWidth: 22
                                            implicitHeight: 22
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4
                                            Label {
                                                text: "All current NSE cash-equity stocks"
                                                color: window.textColor
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                            }
                                            Label {
                                                text: "Sector folders · CSV resume · current listings only"
                                                color: window.mutedColor
                                                font.pixelSize: 10
                                            }
                                        }
                                        Rectangle {
                                            Layout.preferredWidth: 17
                                            Layout.preferredHeight: 17
                                            color: parent.parent.checked ? window.accentColor : "transparent"
                                            border.color: parent.parent.checked ? window.accentColor : window.borderColor
                                            radius: 1
                                            Text {
                                                anchors.centerIn: parent
                                                text: "✓"
                                                visible: parent.parent.parent.checked
                                                color: "#ffffff"
                                                font.pixelSize: 11
                                            }
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !controller.busy
                                        onClicked: controller.setSelected(
                                            "stocks",
                                            !parent.checked
                                        )
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Repeater {
                                        model: [
                                            ["SERIES", "EQ only"],
                                            ["ORGANIZATION", "Sector-wise"],
                                            ["RESUME", "Latest CSV date"]
                                        ]
                                        delegate: Rectangle {
                                            required property var modelData
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 52
                                            color: window.raisedColor
                                            border.color: window.borderColor
                                            radius: 2
                                            ColumnLayout {
                                                anchors.fill: parent
                                                anchors.margins: 8
                                                spacing: 2
                                                Eyebrow { text: modelData[0] }
                                                Label {
                                                    text: modelData[1]
                                                    color: window.textColor
                                                    font.pixelSize: 10
                                                }
                                            }
                                        }
                                    }
                                }

                                Label {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    text: "The first sector lookup can take time. The app will show the number of stocks and ask before using a saved NSE list or starting a large job."
                                    color: window.mutedColor
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                    verticalAlignment: Text.AlignBottom
                                }
                            }
                        }

                        Item {
                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 12
                                Label {
                                    text: "Listed options"
                                    color: window.textColor
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                }
                                Label {
                                    text: "Use the current Upstox instrument master for supported index and F&O-stock contracts."
                                    color: window.mutedColor
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 92
                                    property bool checked: controller.selectedKeys.includes("options")
                                    color: checked ? window.accentSoftColor : window.raisedColor
                                    border.color: checked ? window.accentColor : window.borderColor
                                    radius: 2
                                    Behavior on color { ColorAnimation { duration: 120 } }
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 12
                                        Glyph {
                                            name: "options"
                                            tint: window.accentColor
                                            implicitWidth: 22
                                            implicitHeight: 22
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4
                                            Label {
                                                text: "All currently listed contracts"
                                                color: window.textColor
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                            }
                                            Label {
                                                text: "Weekly + monthly · every strike · CE + PE"
                                                color: window.mutedColor
                                                font.pixelSize: 10
                                            }
                                        }
                                        Rectangle {
                                            Layout.preferredWidth: 17
                                            Layout.preferredHeight: 17
                                            color: parent.parent.checked ? window.accentColor : "transparent"
                                            border.color: parent.parent.checked ? window.accentColor : window.borderColor
                                            radius: 1
                                            Text {
                                                anchors.centerIn: parent
                                                text: "✓"
                                                visible: parent.parent.parent.checked
                                                color: "#ffffff"
                                                font.pixelSize: 11
                                            }
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: !controller.busy
                                        onClicked: controller.setSelected(
                                            "options",
                                            !parent.checked
                                        )
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 86
                                    color: window.raisedColor
                                    border.color: window.borderColor
                                    radius: 2
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 10
                                        Glyph {
                                            name: "options"
                                            tint: window.warningColor
                                        }
                                        Label {
                                            Layout.fillWidth: true
                                            text: "Large request set. The app will show a contract count and ask for confirmation before scheduling downloads."
                                            color: window.mutedColor
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                        }
                                    }
                                }
                                Item { Layout.fillHeight: true }
                            }
                        }
                    }

                    SequentialAnimation {
                        id: tabFade
                        NumberAnimation { target: dataPages; property: "opacity"; to: 0.72; duration: 65 }
                        NumberAnimation { target: dataPages; property: "opacity"; to: 1; duration: 100 }
                    }
                    Connections {
                        target: dataTabs
                        function onCurrentIndexChanged() { tabFade.restart() }
                    }
                }
            }

            SurfacePanel {
                Layout.preferredWidth: 390
                Layout.fillHeight: true
                Layout.minimumWidth: 350
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Job configuration"
                            color: window.textColor
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            text: "5 MIN"
                            color: window.mutedColor
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                        }
                    }

                    Eyebrow { text: "UPSTOX ACCESS TOKEN" }
                    TextField {
                        id: tokenField
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        placeholderText: "Paste access token"
                        echoMode: TextInput.Password
                        selectByMouse: true
                        enabled: !controller.busy
                        color: window.textColor
                        placeholderTextColor: window.mutedColor
                        leftPadding: 10
                        background: Rectangle {
                            color: window.fieldColor
                            border.color: tokenField.activeFocus
                                ? window.accentColor : window.borderColor
                            radius: 2
                            Behavior on color { ColorAnimation { duration: 140 } }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: "Kept in memory only. It is not stored in job history."
                        color: window.mutedColor
                        font.pixelSize: 9
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        DatePickerField {
                            Layout.fillWidth: true
                            label: "INITIAL START"
                            dateValue: window.initialStartDate
                            optional: true
                            fieldEnabled: !controller.busy
                            onDateSelected: function(value) {
                                window.initialStartDate = value
                            }
                        }
                        DatePickerField {
                            Layout.fillWidth: true
                            label: "END DATE"
                            dateValue: window.endDate
                            fieldEnabled: !controller.busy
                            onDateSelected: function(value) {
                                window.endDate = value
                            }
                        }
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "Existing CSVs resume from their latest date. Start date applies only to new files."
                        color: window.mutedColor
                        font.pixelSize: 9
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Eyebrow { text: "PARALLEL WORKERS" }
                        Item { Layout.fillWidth: true }
                        ComboBox {
                            id: workerCount
                            Layout.preferredWidth: 76
                            Layout.preferredHeight: 32
                            model: [1, 2, 3, 4, 5, 6, 7, 8]
                            currentIndex: 2
                            enabled: !controller.busy
                            contentItem: Text {
                                leftPadding: 9
                                text: workerCount.displayText
                                color: window.textColor
                                font.pixelSize: 11
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                color: window.fieldColor
                                border.color: window.borderColor
                                radius: 2
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 1
                        color: window.borderColor
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Progress"
                            color: window.textColor
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                        Item { Layout.fillWidth: true }
                        Label {
                            text: Math.round(controller.progressValue * 100) + "%"
                            color: window.accentColor
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                        }
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 5
                        value: controller.progressValue
                        background: Rectangle { color: window.borderColor }
                        contentItem: Item {
                            Rectangle {
                                width: parent.width * controller.progressValue
                                height: parent.height
                                color: window.accentColor
                                Behavior on width { NumberAnimation { duration: 180 } }
                            }
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        text: controller.statusMessage
                        color: controller.statusKind === "error" ? window.errorColor
                            : controller.statusKind === "success" ? window.successColor
                            : controller.statusKind === "warning" ? window.warningColor
                            : window.mutedColor
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Item { Layout.fillWidth: true }
                        FlatButton {
                            visible: controller.canCancel
                            text: "Cancel"
                            enabled: controller.canCancel
                            onClicked: controller.cancelDownload()
                        }
                        FlatButton {
                            id: downloadButton
                            primary: true
                            Layout.preferredWidth: 156
                            text: controller.busy ? "Working..." : "Start download"
                            enabled: !controller.busy && controller.selectedCount > 0
                            onClicked: controller.startDownload(
                                tokenField.text,
                                window.initialStartDate,
                                window.endDate,
                                workerCount.currentValue
                            )
                            contentItem: RowLayout {
                                spacing: 8
                                Item { Layout.fillWidth: true }
                                Glyph {
                                    name: "download"
                                    tint: downloadButton.enabled ? "#ffffff" : window.mutedColor
                                }
                                Label {
                                    text: parent.parent.text
                                    color: downloadButton.enabled ? "#ffffff" : window.mutedColor
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }
        }

        SurfacePanel {
            Layout.fillWidth: true
            Layout.preferredHeight: 174
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Glyph { name: "refresh"; tint: window.accentColor }
                    Label {
                        text: "Recent jobs"
                        color: window.textColor
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }
                    Label {
                        text: "Saved locally · select an unfinished job to resume"
                        color: window.mutedColor
                        font.pixelSize: 10
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "Refresh"
                        flat: true
                        enabled: !controller.busy
                        onClicked: controller.refreshJobs()
                        contentItem: RowLayout {
                            spacing: 6
                            Glyph { name: "refresh"; tint: window.mutedColor }
                            Label {
                                text: "Refresh"
                                color: window.textColor
                                font.pixelSize: 10
                            }
                        }
                    }
                    FlatButton {
                        text: "Resume selected"
                        enabled: controller.canResume
                        onClicked: controller.resumeJob(tokenField.text)
                    }
                }

                ListView {
                    id: jobList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    orientation: ListView.Horizontal
                    spacing: 8
                    clip: true
                    model: controller.recentJobs
                    ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                    delegate: Rectangle {
                        required property var modelData
                        width: 250
                        height: 100
                        property bool selected: controller.selectedJobId === modelData.jobId
                        color: selected ? window.accentSoftColor : window.raisedColor
                        border.color: selected ? window.accentColor : window.borderColor
                        radius: 2
                        Behavior on color { ColorAnimation { duration: 120 } }
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 9
                            spacing: 4
                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    Layout.fillWidth: true
                                    text: modelData.status.toUpperCase()
                                    color: modelData.statusCode === "completed" ? window.successColor
                                        : modelData.statusCode === "completed_with_errors" ? window.warningColor
                                        : modelData.statusCode === "cancelled" ? window.errorColor
                                        : window.accentColor
                                    font.pixelSize: 9
                                    font.weight: Font.Bold
                                }
                                Label {
                                    text: modelData.createdAt
                                    color: window.mutedColor
                                    font.pixelSize: 9
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                text: modelData.summary
                                color: window.textColor
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                            ProgressBar {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 4
                                value: modelData.completedItems / Math.max(1, modelData.totalItems)
                                background: Rectangle { color: window.borderColor }
                                contentItem: Item {
                                    Rectangle {
                                        width: parent.width * (modelData.completedItems / Math.max(1, modelData.totalItems))
                                        height: parent.height
                                        color: window.accentColor
                                    }
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            enabled: !controller.busy
                            onClicked: controller.selectJob(modelData.jobId)
                        }
                    }
                    Label {
                        anchors.centerIn: parent
                        visible: controller.recentJobs.length === 0
                        text: "No saved jobs"
                        color: window.mutedColor
                        font.pixelSize: 11
                    }
                }
            }
        }
    }

    Dialog {
        id: confirmationDialog
        modal: true
        title: "Review download"
        standardButtons: Dialog.NoButton
        anchors.centerIn: parent
        width: Math.min(540, window.width - 48)
        padding: 16

        background: Rectangle {
            color: window.surfaceColor
            radius: 3
            border.color: window.borderColor
        }
        contentItem: ColumnLayout {
            spacing: 14
            Label {
                id: confirmationText
                Layout.fillWidth: true
                text: ""
                color: window.textColor
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                FlatButton {
                    text: "Go back"
                    onClicked: {
                        confirmationDialog.close()
                        controller.confirmPreparation(false)
                    }
                }
                FlatButton {
                    primary: true
                    text: "Continue"
                    onClicked: {
                        confirmationDialog.close()
                        controller.confirmPreparation(true)
                    }
                }
            }
        }
    }

    Connections {
        target: controller
        function onConfirmationRequested(message) {
            confirmationText.text = message
            confirmationDialog.open()
        }
    }

    Timer {
        interval: 3000
        repeat: true
        running: true
        onTriggered: controller.refreshJobs()
    }
}
