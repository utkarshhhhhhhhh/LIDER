module circuit1 (
    input A, B, C, D, E, CLK,
    output OUT
);
    wire and1_out, nand1_out, f1_out, f2_out, nand2_out, f3_out, final_out;

    // Instantiating gates and flip-flops
    AND2_X1 u1 (.A1(D), .A2(E), .ZN(and1_out)); // AND Gate

    DFF_X1 f1 (.D(and1_out), .CK(CLK), .Q(f1_out)); // D Flip-Flop F1

    NAND2_X1 u2 (.A1(C), .A2(f1_out), .ZN(nand1_out)); // NAND Gate

    DFF_X1 f2 (.D(nand1_out), .CK(CLK), .Q(f2_out)); // D Flip-Flop F2

    NAND2_X1 u3 (.A1(B), .A2(f2_out), .ZN(nand2_out)); // NAND Gate

    DFF_X1 f3 (.D(nand2_out), .CK(CLK), .Q(f3_out)); // D Flip-Flop F3

    NAND2_X1 u4 (.A1(A), .A2(f3_out), .ZN(final_out)); // NAND Gate

    assign OUT = final_out;
    
endmodule