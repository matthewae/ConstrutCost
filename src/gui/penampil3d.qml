// Penampil 3D bangunan (gui/penampil3d.py). Data elemen dari model Python `adegan`, kamera & seleksi dari `backend`.
//   Seret kiri  : putar          Seret kanan / tengah : geser
//   Roda mouse  : zoom           Klik : pilih elemen       Dobel klik : fokus ke elemen
import QtQuick
import QtQuick3D

Item {
    id: root

    View3D {
        id: view
        anchors.fill: parent
        camera: kamera
        renderMode: View3D.Offscreen
        environment: SceneEnvironment {
            clearColor: backend.warnaLatar
            backgroundMode: SceneEnvironment.Color
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        Node {
            id: poros
            position: backend.pusat
            eulerRotation: backend.rotasi
            Behavior on position { enabled: backend.animasi; Vector3dAnimation { duration: 450; easing.type: Easing.InOutCubic } }
            Behavior on eulerRotation { enabled: backend.animasi; Vector3dAnimation { duration: 450; easing.type: Easing.InOutCubic } }

            PerspectiveCamera {
                id: kamera
                z: backend.jarak
                clipNear: 0.05
                clipFar: 5000
                fieldOfView: backend.fov
                Behavior on z { enabled: backend.animasi; NumberAnimation { duration: 450; easing.type: Easing.InOutCubic } }
            }
            // lampu ikut kamera: sisi yang menghadap pengguna selalu terang
            DirectionalLight { eulerRotation: Qt.vector3d(-35, -30, 0); brightness: 0.85; ambientColor: Qt.rgba(0.42, 0.42, 0.45, 1) }
        }
        DirectionalLight { eulerRotation: Qt.vector3d(-60, 40, 0); brightness: 0.55 }

        Repeater3D {
            model: adegan
            delegate: Model {
                property string gid: model.gid
                geometry: model.geom
                visible: model.tampil
                pickable: model.klik
                materials: PrincipledMaterial {
                    baseColor: model.warna
                    roughness: 0.82
                    metalness: 0.0
                    emissiveFactor: Qt.vector3d(model.warna.r * model.sinar, model.warna.g * model.sinar, model.warna.b * model.sinar)
                    opacity: model.buram
                    alphaMode: model.buram < 0.999 ? PrincipledMaterial.Blend : PrincipledMaterial.Opaque
                    cullMode: Material.NoCulling
                }
            }
        }

        // besi beton (IfcReinforcingBar) per elemen induk; tampil di mode "Besi beton"
        Repeater3D {
            model: adeganBesi
            delegate: Model {
                property string gid: model.gid
                geometry: model.geom
                visible: model.tampil
                pickable: model.klik
                materials: PrincipledMaterial {
                    baseColor: model.warna
                    roughness: 0.45
                    metalness: 0.35
                    emissiveFactor: Qt.vector3d(model.warna.r * model.sinar, model.warna.g * model.sinar, model.warna.b * model.sinar)
                    cullMode: Material.NoCulling
                }
            }
        }

        TapHandler {
            acceptedButtons: Qt.LeftButton
            onTapped: (titik) => {
                var r = view.pick(titik.position.x, titik.position.y)
                backend.pilih(r.objectHit ? r.objectHit.gid : "")
            }
            onDoubleTapped: (titik) => {
                var r = view.pick(titik.position.x, titik.position.y)
                if (r.objectHit) backend.fokus(r.objectHit.gid)
            }
        }
        HoverHandler {
            id: sorot
            onPointChanged: {
                var r = view.pick(sorot.point.position.x, sorot.point.position.y)
                backend.sorot(r.objectHit ? r.objectHit.gid : "")
            }
            onHoveredChanged: if (!hovered) backend.sorot("")
        }
        DragHandler {
            id: putar
            target: null
            acceptedButtons: Qt.LeftButton
            property point awal
            property vector3d rot
            onActiveChanged: if (active) { awal = centroid.position; rot = backend.rotasi }
            onCentroidChanged: if (active) {
                var dx = centroid.position.x - awal.x
                var dy = centroid.position.y - awal.y
                backend.rotasi = Qt.vector3d(Math.max(-89, Math.min(89, rot.x - dy * 0.35)), rot.y - dx * 0.35, 0)
            }
        }
        DragHandler {
            id: geser
            target: null
            acceptedButtons: Qt.RightButton | Qt.MiddleButton
            property point awal
            property vector3d pos
            onActiveChanged: if (active) { awal = centroid.position; pos = backend.pusat }
            onCentroidChanged: if (active) {
                // 1 piksel layar = lebar dunia yang terlihat di jarak poros / tinggi tampilan
                var k = 2 * backend.jarak * Math.tan(backend.fov * Math.PI / 360) / Math.max(view.height, 1)
                var dx = centroid.position.x - awal.x
                var dy = centroid.position.y - awal.y
                backend.pusat = pos.minus(poros.right.times(dx * k)).plus(poros.up.times(dy * k))
            }
        }
        WheelHandler {
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: (ev) => { backend.zoom(ev.angleDelta.y) }
        }
    }

    Rectangle {
        id: labelSorot
        visible: backend.teksSorot !== "" && sorot.hovered
        x: Math.min(sorot.point.position.x + 16, root.width - width - 8)
        y: Math.max(sorot.point.position.y - height - 10, 8)
        radius: 8
        color: backend.warnaLabel
        border.color: backend.warnaGaris
        width: teksSorot.implicitWidth + 20
        height: teksSorot.implicitHeight + 12
        Text {
            id: teksSorot
            anchors.centerIn: parent
            text: backend.teksSorot
            color: backend.warnaTeks
            font.pixelSize: 12
            textFormat: Text.RichText
        }
    }
}
