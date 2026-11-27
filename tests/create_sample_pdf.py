"""
Generates an authorized multi-page sample academic PDF for testing extraction,
header/footer cleaning, heading detection, and summarization without copyright issues.
"""
from pathlib import Path
import pymupdf as fitz

def generate_sample_academic_pdf(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()

    pages_content = [
        # Page 1
        """1.0 INTRODUCTION TO COMPUTER SYSTEMS

A computer is a high-speed electronic calculating machine that accepts digitized input information, processes it according to a list of internally stored instructions, and produces the resulting output information. The list of instructions is called a computer program and internal storage is called computer memory.

The functional units of a computer system are:
1. Input Unit: Transduces physical signals into digital binary representations (e.g., keyboard, mouse, barcode reader).
2. Central Processing Unit (CPU): Executes stored program instructions. Contains the Arithmetic Logic Unit (ALU) and Control Unit (CU).
3. Memory Unit: Retains program instructions and runtime data operands.
4. Output Unit: Delivers computed results in human-readable or machine-readable format.

Definition: Von Neumann Architecture
The fundamental architectural model where programs and data reside simultaneously in the same physical memory address space. The CPU sequentially fetches, decodes, and executes instructions from this unified memory.""",

        # Page 2
        """1.1 CENTRAL PROCESSING UNIT AND ARITHMETIC UNIT

The CPU is the primary computational engine. It consists of the following components:

1.1.1 Arithmetic and Logic Unit (ALU)
The ALU performs all basic arithmetic operations (addition, subtraction, multiplication, division) and logical decisions (AND, OR, NOT, bit-shift comparisons).

1.1.2 Control Unit (CU)
The Control Unit is the supervisor of all processor activities. It generates clock-synchronized timing and control signals that coordinate instruction fetching, register transfers, and bus transactions.

1.1.3 Internal CPU Registers
Registers provide ultra-fast temporary storage inside the processor core:
- Program Counter (PC): Holds the memory address of the next instruction to be fetched.
- Instruction Register (IR): Holds the currently executing instruction opcode.
- Memory Address Register (MAR): Holds the physical memory address referenced during read/write cycles.
- Memory Buffer Register (MBR): Holds the actual data word read from or to be written to memory.
- Accumulator (AC): Holds intermediate arithmetic operands and results.

Performance Formula: CPU Execution Time
CPU Time = Instruction Count * Cycles Per Instruction (CPI) * Clock Cycle Time""",

        # Page 3
        """1.2 MEMORY HIERARCHY AND PERFORMANCE

Computer memory systems require a balance between speed, storage capacity, and manufacturing cost per bit. No single physical technology satisfies all three constraints simultaneously.

1.2.1 Levels of the Hierarchy
1. Processor Registers: Fastest access (~0.5 - 1 ns), lowest capacity (< 2 KB), highest cost per bit.
2. Primary Cache (L1, L2, L3): High-speed SRAM placed adjacent to the processor core (~1 - 10 ns).
3. Main Memory (RAM): Dynamic RAM (DRAM) offering moderate access latency (~50 - 100 ns) and gigabyte capacities.
4. Secondary Storage: Non-volatile magnetic disks (HDD) and solid-state drives (SSD) with millisecond/microsecond latencies.

Principle of Locality:
- Temporal Locality: If a specific memory location is referenced once, it will likely be referenced again in the near future (e.g., loop control variables).
- Spatial Locality: If a memory location is referenced, nearby locations will likely be referenced soon (e.g., consecutive array traversal).

Formula: Average Memory Access Time (AMAT)
AMAT = Hit Time + (Miss Rate * Miss Penalty)""",

        # Page 4
        """1.3 INPUT-OUTPUT SUBSYSTEMS AND BUS ORGANISATION

Input/Output (I/O) modules act as an intermediary between the CPU/memory internal bus and external peripheral devices.

1.3.1 Data Transfer Modes
1. Programmed I/O: The CPU continuously polls the status flags of the peripheral device until it is ready for transfer (busy waiting). This wastes significant CPU cycles.
2. Interrupt-Driven I/O: The CPU issues a command to the I/O module and resumes executing other tasks. When the device is ready, it signals an interrupt pin on the CPU.
3. Direct Memory Access (DMA): An autonomous DMA controller transfers large contiguous blocks of data directly between peripheral devices and main memory without continuous CPU intervention.

1.4 EXAMINATION REVIEW QUESTIONS [IMP]
1. Explain the Von Neumann stored-program architecture with a clean block diagram. [IMP - 10 Marks]
2. Differentiate between Programmed I/O, Interrupt-driven I/O, and DMA with respect to CPU utilization. [IMP - 10 Marks]
3. Derive the Average Memory Access Time (AMAT) formula and explain the Principle of Locality. [IMP - 5 Marks]"""
    ]

    for idx, page_text in enumerate(pages_content):
        page = doc.new_page(width=595, height=842) # A4 size
        # Running Header (Top Margin)
        page.insert_text((50, 40), "IGNOU BCA — BCS-011: Computer Basics and PC Software", fontsize=9, color=(0.4, 0.4, 0.4))
        # Divider Line
        page.draw_line((50, 48), (545, 48), color=(0.8, 0.8, 0.8), width=0.5)

        # Body Content
        page.insert_textbox((50, 70, 545, 780), page_text, fontsize=10.5, fontname="helv", lineheight=1.4)

        # Running Footer (Bottom Margin)
        page.draw_line((50, 800), (545, 800), color=(0.8, 0.8, 0.8), width=0.5)
        page.insert_text((270, 818), f"Page {idx + 1}", fontsize=9, color=(0.4, 0.4, 0.4))

    doc.save(str(output_path))
    doc.close()
    return output_path

if __name__ == "__main__":
    p = generate_sample_academic_pdf(Path("storage/raw_pdfs/sample_unit.pdf"))
    print(f"Sample PDF created at: {p} ({p.stat().st_size} bytes)")
