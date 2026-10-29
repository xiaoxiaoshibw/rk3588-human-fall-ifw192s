import QtQuick
import QtQuick.Window
import QtQuick3D

Window {
    id: window
    width: 1120
    height: 720
    visible: true
    color: "#0b1220"
    title: "ConsoleV2 · R2 point cloud spike"
    property real sceneAngle: -10

    View3D {
        anchors.fill: parent
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "#0b1220"
            antialiasingMode: SceneEnvironment.NoAA
        }
        PerspectiveCamera {
            position: Qt.vector3d(0, cloudGeometry.radius * 0.24, cloudGeometry.radius * 2.8)
            eulerRotation.x: -5
            clipNear: 0.05
            clipFar: 2000
        }
        Node {
            eulerRotation.y: window.sceneAngle
            Model {
                geometry: cloudGeometry
                eulerRotation.x: -90
                position: Qt.vector3d(-cloudGeometry.center.x, -cloudGeometry.center.z, cloudGeometry.center.y)
                materials: DefaultMaterial {
                    lighting: DefaultMaterial.NoLighting
                    cullMode: DefaultMaterial.NoCulling
                    diffuseColor: "#55d8df"
                    pointSize: 1
                }
            }
        }
    }
    Rectangle {
        x: 24; y: 24
        width: 480; height: 108
        radius: 10
        color: "#da162235"
        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 6
            Text { text: "ConsoleV2 / R2"; color: "white"; font.pixelSize: 22; font.bold: true }
            Text { text: sessionId + "  ·  " + cloudGeometry.pointCount.toLocaleString() + " points"; color: "#b8d1df"; font.pixelSize: 15 }
            Text { text: modeLabel; color: "#f5c27a"; font.pixelSize: 13 }
        }
    }
    Text {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        text: "Read-only source · Qt C++ + C# service · no board access"
        color: "#8ea5b8"
        font.pixelSize: 13
    }
}
