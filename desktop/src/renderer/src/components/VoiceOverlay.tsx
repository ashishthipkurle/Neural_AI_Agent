import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

type VoiceState = "IDLE" | "LISTENING" | "THINKING" | "SPEAKING";

export default function VoiceOverlay() {
    const [voiceState, setVoiceState] = useState<VoiceState>("IDLE");
    const [rms, setRms] = useState(0);

    useEffect(() => {
        // Assume window.electron is available from preload
        const ipc = (window as any).electron?.ipcRenderer;
        if (!ipc) return;

        const unbind = ipc.on("agent:sync", (_event: any, data: any) => {
            if (data.type === "voice_state") {
                setVoiceState(data.state);
                setRms(data.level || 0);
            }
        });
        
        return () => {
            if (unbind) unbind();
        };
    }, []);

    if (voiceState === "IDLE") {
        return null;
    }

    // Siri-like gradients
    const getGradient = () => {
        switch (voiceState) {
            case "LISTENING":
                return "radial-gradient(circle at center, rgba(0,255,255,0.8), rgba(0,100,255,0.4))";
            case "THINKING":
                return "radial-gradient(circle at center, rgba(255,100,200,0.8), rgba(100,0,255,0.4))";
            case "SPEAKING":
                return "radial-gradient(circle at center, rgba(50,255,100,0.8), rgba(0,150,50,0.4))";
            default:
                return "radial-gradient(circle at center, rgba(255,255,255,0.8), rgba(100,100,100,0.4))";
        }
    };

    // Calculate scale based on RMS, base scale varies by state
    const baseScale = voiceState === "THINKING" ? 1.0 : (voiceState === "LISTENING" ? 1.2 : 1.1);
    const dynamicScale = baseScale + (rms * 1.5);

    return (
        <div style={{
            position: "fixed",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "transparent",
            overflow: "hidden"
        }}>
            <motion.div
                animate={{ 
                    scale: dynamicScale,
                    rotate: voiceState === "THINKING" ? 360 : 0
                }}
                transition={{ 
                    scale: { type: "spring", stiffness: 300, damping: 20 },
                    rotate: { duration: 4, repeat: Infinity, ease: "linear" }
                }}
                style={{
                    width: "150px",
                    height: "150px",
                    borderRadius: "50%",
                    background: getGradient(),
                    boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.37)",
                    backdropFilter: "blur(20px)",
                    WebkitBackdropFilter: "blur(20px)",
                    border: "1px solid rgba(255, 255, 255, 0.18)",
                    filter: "drop-shadow(0 0 20px rgba(0,200,255,0.5))"
                }}
            />
        </div>
    );
}
