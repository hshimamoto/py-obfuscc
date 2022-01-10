#!/usr/bin/env python3
# MIT License Copyright(c) 2021, 2022 Hiroshi Shimamoto

import sys

class Line():
    def __init__(self, line):
        self.orig = line
        # parse
        # has indent?
        self.indent = ''
        if line[0] == '\t':
            self.indent = line[0]
        line = line.strip()
        words = line.split()
        first = words[0]
        self.label = ''
        if first[len(first)-1] == ':':
            self.label = first
            if len(words) > 1:
                print("not supported yet")
                exit(1)
        self.directive = ''
        self.opcode = ''
        self.operands = []
        if first[0] == '.':
            # directive?
            if self.label == '':
                self.directive = first
        elif self.label == '':
            self.opcode = first
            self.operands = words[1:]
        self.line = line
        self.words = words
        self.pres = []
        self.posts = []
        self.modified = ''
        self.comment = ''
    def __str__(self):
        line = self.line
        if self.directive == '':
            line = " ".join(self.words)
        if self.modified != '':
            line = self.modified
        if self.comment != '':
            line = f"{line} # {self.comment}"
        return self.indent + line
    def writeto(self, f):
        for line in self.pres:
            line.writeto(f)
        f.write(str(self) + "\n")
        for line in self.posts:
            line.writeto(f)

def parse_lines(ss):
    lines = []
    for s in ss:
        lines.append(Line(s))
    return lines

class Func():
    def __init__(self, name, startline):
        self.name = name
        self.startline = startline
        self.cfi_offset = None
        self.first = None
        self.top = None
        self.frame_start = None
        self.frame_end = None
        self.frame_alloc = None
        self.frame_restore = None
        self.rets = []
        self.lines = []
        self.regs = []
        startline.comment = f"start function {name}"

class Target():
    def __init__(self, src):
        # read source file
        self.src = src
        self.dst = src + ".obfus.s"
    def save(self):
        with open(self.dst, "w") as f:
            for line in self.lines:
                line.writeto(f)

    def analyze(self):
        # read all lines
        with open(self.src, "r") as f:
            self.lines = parse_lines(f.readlines())
        # extract functions
        section = ''
        self.functions = []
        self.ident = None
        currfunc = None
        for line in self.lines:
            if line.directive == '.text':
                section = 'text'
            elif line.directive == '.section':
                section = line.words[1]
            line.section = section
            if line.directive == '.ident':
                self.ident = line
            if line.directive == '.type':
                # .type	main, @function
                typedef = (line.words[1].strip(','), line.words[2])
                print(typedef)
                if typedef[1] == '@function':
                    currfunc = Func(typedef[0], line)
                    self.functions.append(currfunc)
            if line.directive == '.cfi_startproc':
                if currfunc == None:
                    print("detect unknown function")
                    currfunc = Func('', line)
                    self.functions.append(currfunc)
                currfunc.cfi_startproc = line
            if line.directive == '.cfi_offset':
                currfunc.cfi_offset = line

            if currfunc != None:
                line.func = currfunc
                currfunc.lines.append(line)
                if line.opcode != '':
                    if currfunc.first == None:
                        currfunc.first = line
                        print(f"{currfunc.name} {line.opcode}")
                    if currfunc.cfi_offset != None and currfunc.top == None:
                        currfunc.top = line
                if line.opcode == 'ret':
                    currfunc.rets.append(line)

            if line.directive == '.cfi_endproc':
                currfunc.cfi_endproc = line
                currfunc = None

        for f in self.functions:
            # link ops
            prev = None
            for line in f.lines:
                if prev != None:
                    line.prev = prev
                    prev.next = line
                prev = line
            # get all registers using in this function
            regs = []
            for line in f.lines:
                if line.opcode == '':
                    continue
                for r in line.operands:
                    reg = ''
                    for c in r:
                        if c == '%':
                            reg = c
                            continue
                        if c == ',' or c == ')':
                            if reg != '':
                                regs.append(reg)
                            reg = ''
                            continue
                        if reg != '':
                            reg += c
                    if reg != '':
                        regs.append(reg)
            f.regs = list(set(regs))
            print(f.regs)
            # find the frame info
            for line in f.lines:
                if f.frame_start == None:
                    if line.opcode == 'movq':
                        if line.operands[0] == '%rsp,' and line.operands[1] == '%rbp':
                            f.frame_start = line
                if f.frame_end == None:
                    if line.opcode == 'leave':
                        f.frame_end = line
                if f.frame_alloc == None:
                    if line.opcode == 'subq':
                        if line.operands[1] == '%rsp':
                            f.frame_alloc = line
                if f.frame_restore == None:
                    if f.frame_end != None:
                        f.frame_restore = f.frame_end
                    elif line.opcode == 'addq':
                        if line.operands[1] == '%rsp':
                            f.frame_restore = line
            if f.frame_start != None:
                f.frame_start.comment = "frame start"
            if f.frame_end != None:
                f.frame_end.comment = "frame end"
            if f.frame_alloc != None:
                f.frame_alloc.comment = "frame alloc"
            if f.frame_restore != None:
                if f.frame_end == f.frame_restore:
                    f.frame_restore.comment = "frame restore end"
                else:
                    f.frame_restore.comment = "frame restore"

    def obfuscate_simple(self):
        for f in self.functions:
            for line in f.lines:
                op = line.opcode
                if op != 'call':
                    continue
                ss = [
                        "jmp 1f",
                        ".byte 0x48, 0xb8, 0x12, 0x34, 0x56",
                        "1:",
                    ]
                line.pres.extend(parse_lines(ss))

    def modify_indirect_base(self, func, line, base):
        b = [0x48, 0xb8]
        if line.opcode == 'call':
            b.extend([0x00, 0x00])
        ss = [
                f"push %rax",
            ]
        if base != '':
            ss.extend([
                    f"mov 1f(%rip), %rax",
                    f"add {base}, %rax",
                ])
        else:
            ss.extend([
                    f"lea {func.name}(%rip), %rax",
                    f"add 1f(%rip), %rax",
                ])
        ss.extend([
                f"je 2f",
                f"jmp *%rax",
                f".data",
                f"1:",
                f".quad 3f-{func.name}",
                f".previous",
                f"2:",
                f"pop %rax", # dummy
                f".byte " + ", ".join(list(map(hex, b))),
                f"3:",
                f"pop %rax",
            ])
        line.pres.extend(parse_lines(ss))

    def obfuscate_indirect_simple(self):
        for f in self.functions:
            p = f.frame_alloc
            if p == None:
                continue
            for line in f.lines:
                if line.opcode != 'call':
                    continue
                self.modify_indirect_base(f, line, '')

    def obfuscate_movq_regs(self):
        for f in self.functions:
            p = f.frame_alloc
            if p == None:
                continue
            for line in f.lines:
                # movq %rax, %rdi
                opcode = line.opcode
                if opcode != 'movq' and opcode != 'movl':
                    continue
                op0 = line.operands[0].strip(',')
                op1 = line.operands[1]
                print(f"check {opcode} {op0} {op1}")
                if op0[0] != '%':
                    continue
                if op1[0] != '%':
                    continue
                if ':' in op0:
                    continue
                if ':' in op1:
                    continue
                if opcode == 'movl':
                    print("use 64bit reg")
                    promote = lambda x: x.strip('d') if x[1] == 'r' else "%r" + x[2:]
                    op0 = promote(op0)
                    op1 = promote(op1)
                if op0 == '%rsp':
                    continue
                if op1 == '%rsp':
                    continue
                print(f"replace with push/pop")
                gpregs = ['%rax', '%rcx', '%rdx', '%rbx', '%RSP', '%rbp', '%rsi', '%rdi']
                gp = True
                if not op0 in gpregs:
                    gp = False
                if not op1 in gpregs:
                    gp = False
                line.modified = "#" + line.orig.strip()
                if not gp:
                    # movq $XXXX, gp1
                    line.posts.extend(parse_lines([
                        f"pushq {op0}",
                        f"popq {op1}"]))
                else:
                    b0 = 0xb8
                    for r in gpregs:
                        if op1 == r:
                            break
                        b0 += 1
                    line.posts.extend(parse_lines([
                        f".byte 0x{b0:x}",
                        f"1:",
                        f"pushq {op0}",
                        f"popq {op1}",
                        f"jmp 2f",
                        f"jmp 1b",
                        f"2:"]))

    def obfuscate_indirect_base(self):
        for f in self.functions:
            p = f.frame_alloc
            if p == None:
                continue
            base = '%rbx'
            if base in f.regs:
                print(f"unable to use {base}")
                continue
            # reserve
            alloc = f.frame_alloc
            restore = f.frame_restore
            if alloc == None or restore == None:
                print("unable to frame handling")
                continue
            # alloc -> subq $16, %rsp
            sz = int(alloc.operands[0].strip(',')[1:])
            print(f"frame size = {sz} -> {sz+16}")
            sz += 16
            # change alloc line
            alloc.modified = f"subq ${sz}, %rsp"
            alloc.posts.extend(parse_lines([
                f"movq %rbx, (%rsp)",
                f"leaq {f.name}(%rip), %rbx"]))
            # check restore
            if restore.opcode == 'leave':
                pass # ok nothing to do
            if restore.opcode == 'addq':
                print(f"orig restore: {restore.line}")
                # change restore line
                restore.modified = f"addq ${sz}, %rsp"
            restore.pres.extend(parse_lines(["movq (%rsp), %rbx"]))
            for line in f.lines:
                if line.opcode != 'call':
                    continue
                self.modify_indirect_base(f, line, base)

def main():
    if len(sys.argv) != 2:
        exit(1)
    src = sys.argv[1]
    target = Target(src)
    target.analyze()
    target.obfuscate_indirect_simple()
    target.obfuscate_movq_regs()
    target.save()

if __name__ == '__main__':
    main()
