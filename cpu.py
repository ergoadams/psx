class cpu:
    def __init__(self, bus, data):
        self.pc = 0xBFC00000
        self.next_pc = (self.pc + 4) & 0xFFFFFFFF
        self.current_pc = 0
        self.cause = 0
        self.epc = 0
        self.data = data
        self.bus = bus
        self.opcodes = {0: 0, 1: self.op_bxx, 2: self.op_j, 3: self.op_jal, 4: self.op_beq, 5: self.op_bne, 6: self.op_blez, 7: self.op_bgtz, 8: self.op_addi, 9: self.op_addiu, 10: self.op_slti, 11: self.op_sltiu, 12: self.op_andi, 13: self.op_ori, 14: self.op_xori, 15: self.op_lui, 16: self.op_cop0, 17: self.op_cop1, 18: self.op_cop2, 19: self.op_cop3, 32: self.op_lb, 33: self.op_lh, 34: self.op_lwl, 35: self.op_lw, 36: self.op_lbu, 37: self.op_lhu, 38: self.op_lwr, 40: self.op_sb, 41: self.op_sh, 42: self.op_swl, 43: self.op_sw, 46: self.op_swr, 48: self.op_lwc0, 49: self.op_lwc1, 50: self.op_lwc2, 51: self.op_lwc3, 56: self.op_swc0, 57: self.op_swc1, 58: self.op_swc2, 59: self.op_swc3}
        self.opcodes2 = {0: self.op_sll, 2: self.op_srl, 3: self.op_sra, 4: self.op_sllv, 6: self.op_srlv, 7: self.op_srav, 8: self.op_jr, 9: self.op_jalr, 12: self.op_syscall, 13: self.op_break, 16: self.op_mfhi, 17: self.op_mthi, 18: self.op_mflo, 19: self.op_mtlo, 24: self.op_mult, 25: self.op_multu, 26: self.op_div, 27: self.op_divu, 32: self.op_add, 33: self.op_addu, 34: self.op_sub, 35: self.op_subu, 36: self.op_and, 37: self.op_or, 38: self.op_xor, 39: self.op_nor, 42: self.op_slt, 43: self.op_sltu}
        self.cop_ops = {0: self.op_mfc0, 4: self.op_mtc0, 16: self.op_rfe}
        self.next_instruction = 0
        self.regs = [0xdeadbeef] * 32
        self.regs[0] = 0
        self.regnames = ["$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3", "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7", "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"]
        self.outregs = [0] * 32
        self.load = (0, 0)
        self.sr = 0
        self.hi = 0xdeadbeef
        self.lo = 0xdeadbeef
        self.branchbool = False
        self.delay_slot = False
        self.running = True

        self.exc_syscall = 0x8
        self.exc_overflow = 0xC
        self.exc_loadaddresserror = 0x4
        self.exc_storeaddresserror = 0x5
        self.exc_break = 0x9
        self.exc_coprocessorerror = 0xB
        self.exc_illegalinstruction = 0xA

    def clock(self):
        self.current_pc = self.pc
        if self.current_pc % 4 != 0:
            return self.exception(self.exc_loadaddresserror)

        self.instruction = self.load32(self.pc)
        self.delay_slot = self.branchbool
        self.branchbool = False
        self.pc = self.next_pc
        self.next_pc = (self.pc + 4) & 0xFFFFFFFF
        reg, val = self.load[0], self.load[1]
        self.set_reg(reg, val)
        self.load = (0, 0)
        self.decode_and_execute(self.instruction)
        self.regs = self.outregs[:]

    def exception(self, cause):
        handler = 0xBFC00180 if (self.sr & (1 << 22)) else 0x80000080
        mode = self.sr & 0x3F
        self.sr &= ~0x3F
        self.sr |= (mode << 2) & 0x3F
        self.cause &= ~0x7C
        self.cause |= (cause & 0xFFFFFFFF) << 2
        self.epc = self.current_pc
        if self.delay_slot:
            self.epc = (self.epc - 4) & 0xFFFFFFFF
            self.cause |= 1 << 31
        else:
            self.cause &= ~(1 << 31)

        self.pc = handler
        self.next_pc = (self.pc + 4) & 0xFFFFFFFF


    def load32(self, addr):
        return self.bus.load32(addr)

    def load16(self, addr):
        return self.bus.load16(addr)

    def load8(self, addr):
        return self.bus.load8(addr)

    def store32(self, addr, value):
        self.bus.store32(addr, value)

    def store16(self, addr, value):
        self.bus.store16(addr, value)

    def store8(self, addr, value):
        self.bus.store8(addr, value)

    def set_reg(self, index, value):
        self.outregs[index] = value
        self.outregs[0] = 0

    def read_reg(self, index):
        return self.regs[index]

    def imm_se(self):
        sign_bit = 1 << 15
        return (self.instruction & (sign_bit - 1)) - (self.instruction & sign_bit)

    def imm_jump(self):
        return self.instruction & 0x3FFFFFF

    def op_lui(self):
        self.set_reg(self.t, self.imm << 16)

    def op_ori(self):
        self.set_reg(self.t, self.read_reg(self.s) | self.imm)

    def op_sw(self):
        if self.sr & 0x10000:
            #print("IGNORING STORE WHILE CACHE IS ISOLATED")
            return
        addr = (self.read_reg(self.s) + self.imm_se()) & 0xFFFFFFFF
        if addr % 4 == 0:
            self.store32(addr, self.read_reg(self.t))
        else:
            self.exception(self.exc_storeaddresserror)

    def op_sll(self):
        self.set_reg(self.d, self.read_reg(self.t) << self.shift)

    def op_addiu(self):
        self.set_reg(self.t, (self.read_reg(self.s) + self.imm_se()) & 0xFFFFFFFF)

    def op_j(self):
        self.next_pc = (self.pc & 0xF0000000) | (self.imm_jump() << 2)
        self.branchbool = True

    def op_or(self):
        self.set_reg(self.d, self.read_reg(self.s) | self.read_reg(self.t))

    def op_cop0(self):
        self.cop_ops[self.s]()

    def op_mtc0(self):
        v = self.read_reg(self.t)
        if self.d in (3, 5, 6, 7, 9, 11):
            if v != 0:
                print("UNHANDLED WRITE TO COP0R", self.d)
        elif self.d == 12:
            self.sr = v
        elif self.d == 13:
            if v != 0:
                print("UNHANDLED WRITE TO CAUSE REGISTER")
        else:
            print("UNHANDLED COP0 REGISTER", self.d)

    def branch(self, offset):
        self.next_pc = (self.next_pc + (offset << 2) - 4) & 0xFFFFFFFF
        self.branchbool = True

    def op_bne(self):
        if self.read_reg(self.s) != self.read_reg(self.t):
            self.branch(self.imm_se())

    def op_addi(self):
        i = self.imm_se()
        s = self.read_reg(self.s)
        v = s + i
        if ((v ^ s) & (v ^ i)) & 0x80000000 != 0:
            self.exception(self.exc_overflow)
        else:
            self.set_reg(self.t, v & 0xFFFFFFFF)

    def op_lw(self):
        if self.sr & 0x10000 != 0:
            print("IGNORING LOAD WHILE CACHE IS ISOLATED")
            return
        addr = (self.read_reg(self.s) + self.imm_se()) & 0xFFFFFFFF
        if addr % 4 == 0:
            self.load = (self.t, self.load32(addr))
        else:
            self.exception(self.exc_loadaddresserror)

    def op_sltu(self):
        self.set_reg(self.d, 1 if (self.read_reg(self.s) < self.read_reg(self.t)) else 0)

    def op_addu(self):
        self.set_reg(self.d, (self.read_reg(self.s) + self.read_reg(self.t)) & 0xFFFFFFFF)

    def op_sh(self):
        if self.sr & 0x10000 != 0:
            print("INGORING STORE WHILE CACHE IS ISOLATED")
            return
        addr = (self.read_reg(self.s) + self.imm_se()) & 0xFFFFFFFF
        if addr % 2 == 0:
            self.store16(addr, self.read_reg(self.t))
        else:
            self.exception(self.exc_storeaddresserror)

    def op_jal(self):
        ra = self.next_pc
        self.op_j()
        self.set_reg(31, ra)
        self.branchbool = True

    def op_andi(self):
        self.set_reg(self.t, self.read_reg(self.s) & self.imm)

    def op_sb(self):
        if self.sr & 0x10000 != 0:
            print("INGNORING STORE WHILE CACHE IS ISOLATED")
            return
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        v = self.read_reg(self.t)
        sign_bit = 1 << 7
        v = (v & (sign_bit - 1)) - (v & sign_bit)
        self.store8(addr, v)

    def op_jr(self):
        s = self.s
        self.next_pc = self.read_reg(s)
        self.branchbool = True

    def op_lb(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        v = self.load8(addr)
        sign_bit = 1 << 7
        v = (v & (sign_bit - 1)) - (v & sign_bit)
        self.load = (self.t, v & 0xFFFFFFFF)

    def op_beq(self):
        i = self.imm_se()
        if self.read_reg(self.s) == self.read_reg(self.t):
            self.branch(i)

    def op_mfc0(self):
        if self.d == 12:
            self.load = (self.t, self.sr)
        elif self.d == 13:
            self.load = (self.t, self.cause)
        elif self.d == 14:
            self.load = (self.t, self.epc)
        else:
            print("UNHANDLED READ FROM COP0R", self.d)


    def op_and(self):
        v = self.read_reg(self.s) & self.read_reg(self.t)
        self.set_reg(self.d, v)

    def op_add(self):
        s = self.read_reg(self.s)
        t = self.read_reg(self.t)
        v = s + t
        if ((v ^ s) & (v ^ t)) & 0x80000000 != 0:
            self.exception(self.exc_overflow)
        else:
            v & 0xFFFFFFFF
            self.set_reg(self.d, v)

    def op_bgtz(self):
        i = self.imm_se()
        v = ((self.read_reg(self.s) & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000
        if v > 0:
            self.branch(i)

    def op_blez(self):
        i = self.imm_se()
        v = ((self.read_reg(self.s) & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000
        if v <= 0:
            self.branch(i)

    def op_lbu(self):
        i = self.imm_se()
        self.load = (self.t, self.load8((self.read_reg(self.s) + i) & 0xFFFFFFFF))

    def op_jalr(self):
        self.set_reg(self.d, self.next_pc)
        self.next_pc = self.read_reg(self.s)
        self.branchbool = True

    def op_bxx(self):
        i = self.imm_se()
        is_bgez = (self.instruction >> 16) & 1
        is_link = ((self.instruction >> 17) & 0xF) == 0x8
        v = ((self.read_reg(self.s) & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000
        test = 1 if (v < 0) else 0
        test = test ^ is_bgez
        if is_link:
            self.set_reg(31, self.next_pc)
        if test:
            self.branch(i)

    def op_slti(self):
        i = self.imm_se()
        v = ((self.read_reg(self.s) & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000
        self.set_reg(self.t, 1 if (v < i) else 0)

    def op_subu(self):
        self.set_reg(self.d, (self.read_reg(self.s) - self.read_reg(self.t)) & 0xFFFFFFFF)

    def op_sra(self):
        v = (((self.read_reg(self.t) ^ 0x80000000) - 0x80000000) >> self.shift) & 0xFFFFFFFF
        self.set_reg(self.d, v)

    def op_div(self):
        n = (self.read_reg(self.s) ^ 0x80000000) - 0x80000000
        d = (self.read_reg(self.t) ^ 0x80000000) - 0x80000000
        if not d:
            self.hi = n & 0xFFFFFFFF
            self.lo = 0xFFFFFFFF if (n >= 0) else 1
        elif (n & 0xFFFFFFFF) == 0x80000000 and d == -1:
            self.hi = 0
            self.lo = 0x80000000
        else:
            self.hi = (n % d) & 0xFFFFFFFF
            self.lo = (n // d) & 0xFFFFFFFF

    def op_mflo(self):
        self.set_reg(self.d, self.lo)

    def op_srl(self):
        self.set_reg(self.d, self.read_reg(self.t) >> self.shift)

    def op_sltiu(self):
        i = self.imm_se()
        self.set_reg(self.t, 1 if (self.read_reg(self.s) < i) else 0)

    def op_divu(self):
        n = self.read_reg(self.s)
        d = self.read_reg(self.t)
        if not d:
            self.hi = n
            self.lo = 0xFFFFFFFF
        else:
            self.hi = n % d
            self.lo = n // d

    def op_mfhi(self):
        self.set_reg(self.d, self.hi)

    def op_slt(self):
        s = (self.read_reg(self.s) ^ 0x80000000) - 0x80000000
        t = (self.read_reg(self.t) ^ 0x80000000) - 0x80000000
        self.set_reg(self.d, 1 if (s < t) else 0)

    def op_syscall(self):
        self.exception(self.exc_syscall)

    def op_mtlo(self):
        self.lo = self.read_reg(self.s)

    def op_mthi(self):
        self.hi = self.read_reg(self.s)

    def op_rfe(self):
        if self.instruction & 0x3F != 16:
            print("INVALID COP0 INSTRUCTION")
            return
        self.sr &= ~0xF
        self.sr |= (self.sr & 0x3F) >> 2

    def op_lhu(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        if addr % 2 == 0:
            self.load = (self.t, self.load16(addr))
        else:
            self.exception(self.exc_loadaddresserror)

    def op_sllv(self):
        v = self.read_reg(self.t) << (self.read_reg(self.s) & 0x1F)
        self.set_reg(self.d, v)

    def op_lh(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        v = (self.load16(addr) ^ 0x8000) - 0x8000
        self.load = (self.t, v & 0xFFFFFFFF)

    def op_nor(self):
        v = ~(self.read_reg(self.s) | self.read_reg(self.t))
        self.set_reg(self.d, v)

    def op_srav(self):
        v = ((self.read_reg(self.t) ^ 0x80000000) - 0x80000000) >> (self.read_reg(self.s) & 0x1F)
        self.set_reg(self.d, v & 0xFFFFFFFF)

    def op_srlv(self):
        v = self.read_reg(self.t) >> (self.read_reg(self.s) & 0x1F)
        self.set_reg(self.d, v)

    def op_multu(self):
        v = self.read_reg(self.s) * self.read_reg(self.t)
        self.hi = (v >> 32) & 0xFFFFFFFF
        self.lo = v & 0xFFFFFFFF

    def op_xor(self):
        v = self.read_reg(self.s) ^ self.read_reg(self.t)
        self.set_reg(self.d, v)

    def op_break(self):
        self.exception(self.exc_break)

    def op_mult(self):
        a = (self.read_reg(self.s) ^ 0x80000000) - 0x80000000
        b = (self.read_reg(self.t) ^ 0x80000000) - 0x80000000
        v = (a * b) & 0xFFFFFFFFFFFFFFFF
        self.hi = (v >> 32) & 0xFFFFFFFF
        self.lo = v & 0xFFFFFFFF

    def op_sub(self):
        s = self.read_reg(self.s)
        t = self.read_reg(self.t)
        v = s - t
        if (((v ^ s) & (s ^ t)) & 0x80000000) != 0:
            self.set_reg(self.d, v)
        else:
            self.exception(self.exc_overflow)

    def op_xori(self):
        v = self.read_reg(self.s) ^ self.imm
        self.set_reg(self.t, v)

    def op_cop1(self):
        self.exception(self.exc_coprocessorerror)

    def op_cop3(self):
        self.exception(self.exc_coprocessorerror)

    def op_cop2(self):
        print("UNHANDLED GTE INSTRUCTION", hex(self.instruction))

    def op_lwl(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        temp = addr & 3
        if temp == 0:
            v = (self.outregs[self.t] & 0x00FFFFFF) | (self.load32(addr & ~3) << 24)
        elif temp == 1:
            v = (self.outregs[self.t] & 0x0000FFFF) | (self.load32(addr & ~3) << 16)
        elif temp == 2:
            v = (self.outregs[self.t] & 0x000000FF) | (self.load32(addr & ~3) << 8)
        elif temp == 3:
            v = (self.outregs[self.t] & 0x00000000) | (self.load32(addr & ~3) << 0)
        else:
            print("UNREACHABLE")
        self.load = (self.t, v)

    def op_lwr(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        temp = addr & 3
        if temp == 0:
            v = (self.outregs[self.t] & 0x00000000) | (self.load32(addr & ~3) >> 0)
        elif temp == 1:
            v = (self.outregs[self.t] & 0x000000FF) | (self.load32(addr & ~3) >> 8)
        elif temp == 2:
            v = (self.outregs[self.t] & 0x0000FFFF) | (self.load32(addr & ~3) >> 16)
        elif temp == 3:
            v = (self.outregs[self.t] & 0x00FFFFFF) | (self.load32(addr & ~3) >> 24)
        else:
            print("UNREACHABLE")
        self.load = (self.t, v)

    def op_swl(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        temp = addr & 3
        if temp == 0:
            mem = (self.load32(addr & ~3) & 0xFFFFFF00) | (self.read_reg(self.t) >> 24)
        elif temp == 1:
            mem = (self.load32(addr & ~3) & 0xFFFF0000) | (self.read_reg(self.t) >> 16)
        elif temp == 2:
            mem = (self.load32(addr & ~3) & 0xFF000000) | (self.read_reg(self.t) >> 8)
        elif temp == 3:
            mem = (self.load32(addr & ~3) & 0x00000000) | (self.read_reg(self.t) >> 0)
        else:
            print("UNREACHABLE")
        self.store32(addr, mem)

    def op_swr(self):
        i = self.imm_se()
        addr = (self.read_reg(self.s) + i) & 0xFFFFFFFF
        temp = addr & 3
        if not temp:
            mem = (self.load32(addr & ~3) & 0x00000000) | (self.read_reg(self.t) << 0)
        elif temp == 1:
            mem = (self.load32(addr & ~3) & 0x000000FF) | (self.read_reg(self.t) << 8)
        elif temp == 2:
            mem = (self.load32(addr & ~3) & 0x0000FFFF) | (self.read_reg(self.t) << 16)
        elif temp == 3:
            mem = (self.load32(addr & ~3) & 0x00FFFFFF) | (self.read_reg(self.t) << 24)
        else:
            print("UNREACHABLE")
        self.store32(addr, mem)

    def op_lwc0(self):
        self.exception(self.exc_coprocessorerror)

    def op_lwc1(self):
        self.exception(self.exc_coprocessorerror)

    def op_lwc2(self):
        print("UNHANDLED GTE LWC", hex(self.instruction))

    def op_lwc3(self):
        self.exception(self.exc_coprocessorerror)

    def op_swc0(self):
        self.exception(self.exc_coprocessorerror)

    def op_swc1(self):
        self.exception(self.exc_coprocessorerror)

    def op_swc2(self):
        print("UNHANDLED GTE SWC", hex(self.instruction))

    def op_swc3(self):
        self.exception(self.exc_coprocessorerror)

    def op_illegal(self):
        print("ILLEGAL INSTRUCTION", hex(self.instruction))
        self.exception(self.exc_illegalinstruction)

    def decode_and_execute(self, instruction):
        self.instruction = instruction
        self.function = instruction >> 26
        self.subfunction = instruction & 0x3F
        self.s = (instruction >> 21) & 0x1F
        self.t = (instruction >> 16) & 0x1F
        self.d = (instruction >> 11) & 0x1F
        self.imm = instruction & 0xFFFF
        self.shift = (instruction >> 6) & 0x1F

        #DEBUG
        #print("{0:#0{1}x}".format(instruction,10), '{:12}'.format(str(self.opcodes[self.function]).split(" ")[2]) if self.function != 0 else '{:12}'.format(str(self.opcodes2[self.subfunction]).split(" ")[2]), "{:5}".format(self.regnames[self.s]), "{:5}".format(self.regnames[self.t]), "{:5}".format(self.regnames[self.d]), "{0:#0{1}x}".format(self.imm,6), "{0:#0{1}x}".format(self.pc,10))

        if self.function in self.opcodes:
            if self.function != 0:
                self.opcodes[self.function]()
            else:
                if self.subfunction in self.opcodes2:
                    self.opcodes2[self.subfunction]()
                else:
                    self.op_illegal()
        else:
            self.op_illegal()
